import os
import uuid
import shutil
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form
import imagehash
from PIL import Image

from config import ASSETS_DIR, SUSPICIOUS_DIR
from database import load_db, save_db
from core.image_processing import compute_hashes, get_blur_index, check_screenshot_borders
from core.scoring import map_distance_to_confidence

router = APIRouter()

@router.post("/register")
async def register(file: UploadFile = File(...), asset_id: Optional[str] = Form(None)):
    if not asset_id:
        asset_id = str(uuid.uuid4())
    
    file_path = os.path.join(ASSETS_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    phash, dhash, ahash, chash, width, height = compute_hashes(file_path)
    blur_idx = float(get_blur_index(file_path))
    
    db = load_db()
    existing = next((i for i, a in enumerate(db["assets"]) if a["asset_id"] == asset_id), None)
    
    record = {
        "asset_id": asset_id,
        "phash": phash,
        "dhash": dhash,
        "ahash": ahash,
        "chash": chash,
        "width": width,
        "height": height,
        "blur_index": blur_idx,
        "file_path": file_path
    }
    
    if existing is not None:
        db["assets"][existing] = record
    else:
        db["assets"].append(record)
        
    save_db(db)
    
    return {
        "status": "registered",
        "asset_id": asset_id,
        "hash": phash
    }

@router.post("/scan")
async def scan(file: UploadFile = File(...)):
    suspicious_path = os.path.join(SUSPICIOUS_DIR, f"suspicious_{file.filename}")
    with open(suspicious_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    s_phash, s_dhash, s_ahash, s_chash, s_w, s_h = compute_hashes(suspicious_path)
    s_blur = get_blur_index(suspicious_path)
    
    db = load_db()
    
    best_match = None
    best_dist = 999
    
    s_phash_obj = imagehash.hex_to_hash(s_phash)
    s_ahash_obj = imagehash.hex_to_hash(s_ahash)
    
    for asset in db["assets"]:
        a_phash_obj = imagehash.hex_to_hash(asset["phash"])
        a_ahash_obj = imagehash.hex_to_hash(asset.get("ahash", asset["phash"]))
        
        dist_p = s_phash_obj - a_phash_obj
        dist_a = s_ahash_obj - a_ahash_obj
        
        dist = min(dist_p, dist_a)
            
        if dist < best_dist:
            best_dist = int(dist)
            best_match = asset
            
    if best_dist > 20 and best_match is not None:
        try:
            s_img = Image.open(suspicious_path)
            a_img = Image.open(best_match["file_path"])
            dist_c = imagehash.colorhash(s_img) - imagehash.colorhash(a_img)
            if dist_c < 8:
                best_dist = 24 
        except Exception as e:
            pass
            
    confidence, reason = map_distance_to_confidence(best_dist)
    
    if confidence == 0 or best_match is None:
        return {
            "match": False,
            "confidence": 0,
            "matched_asset": None,
            "reason": "Distance exceeded match threshold",
            "modifications": []
        }
        
    modifications = []
    
    s_aspect = s_w / float(s_h)
    a_aspect = best_match["width"] / float(best_match["height"])
    aspect_diff = abs(s_aspect - a_aspect)
    
    if aspect_diff > 0.05: 
        modifications.append("cropped")
        
    if aspect_diff <= 0.05 and (s_w != best_match["width"] or s_h != best_match["height"]):
        modifications.append("resized")
        
    original_blur = best_match.get("blur_index", 1000)
    if s_blur < original_blur * 0.7: 
        modifications.append("compressed")
        
    if check_screenshot_borders(suspicious_path):
         modifications.append("screenshot_borders_detected")
    
    return {
        "match": True,
        "confidence": confidence,
        "matched_asset": best_match["asset_id"],
        "reason": reason,
        "modifications": modifications
    }
