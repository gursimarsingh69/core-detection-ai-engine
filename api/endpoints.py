import os
import uuid
import shutil
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form
import imagehash
from PIL import Image

from config import ASSETS_DIR, SUSPICIOUS_DIR
from database import load_db, save_db
from core.image_processing import compute_hashes, get_blur_index, check_screenshot_borders, orb_feature_match
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
        
    db = load_db()
    
    if not db.get("assets"):
        return {
            "match": False,
            "confidence": 0,
            "matched_asset": None,
            "reason": "No registered assets to compare against.",
            "modifications": []
        }
        
    from core.ai_engine import verify_semantic_match_with_gemini
    ai_result = verify_semantic_match_with_gemini(suspicious_path, db["assets"])
    
    if ai_result:
        return {
            "match": ai_result.get("match", False),
            "confidence": ai_result.get("similarity_score", 0),
            "matched_asset": ai_result.get("matched_asset_id"),
            "reason": ai_result.get("reason", "Analyzed via AI."),
            "modifications": ai_result.get("modifications", [])
        }
    else:
        return {
            "match": False,
            "confidence": 0,
            "matched_asset": None,
            "reason": "AI Engine Unavailable (503 Error) or Failed.",
            "modifications": []
        }
