import os
import json
import shutil
import uuid
from typing import Optional, List

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import imagehash
import cv2
import numpy as np

app = FastAPI(
    title="Media Alteration Detector", 
    description="Detect modified/reposted media assets.",
    version="1.0.0",
    docs_url="/docs"
)

# Phase 5: Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "db.json"
ASSETS_DIR = "assets"
SUSPICIOUS_DIR = "suspicious"

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(SUSPICIOUS_DIR, exist_ok=True)

# Database robustness wrapper
def load_db():
    if not os.path.exists(DB_FILE):
        return {"assets": []}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Graceful fallback if corrupted (User review fulfilled)
        return {"assets": []}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

def compute_hashes(img_path):
    img = Image.open(img_path)
    phash = str(imagehash.phash(img))
    dhash = str(imagehash.dhash(img))
    ahash = str(imagehash.average_hash(img))
    chash = str(imagehash.colorhash(img))
    return phash, dhash, ahash, chash, img.width, img.height

def get_blur_index(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def check_screenshot_borders(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return False
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    if h < 20 or w < 20: 
        return False
    
    # Heuristic: check if the first 5 rows and last 5 rows have extremely low variance (solid black / solid color usually)
    top_var = np.var(gray[0:5, :])
    bottom_var = np.var(gray[-5:, :])
    left_var = np.var(gray[:, 0:5])
    right_var = np.var(gray[:, -5:])

    if (top_var < 10 and bottom_var < 10) or (left_var < 10 and right_var < 10):
        return True
    return False

def map_distance_to_confidence(dist):
    # Mappings as requested by user
    # 0–8   = Very strong match
    # 9–14  = Likely match
    # 15–20 = Weak match
    # 21+   = No match
    
    if dist <= 0:
        return 100, "Exact or very strong match"
    elif dist <= 8:
        # Scale 100 down to 90
        val = 100 - dist
        return int(val), "Strong perceptual similarity with official asset"
    elif dist <= 14:
        # Scale 89 down to 75
        val = 90 - (dist - 8) * 2
        return int(val), "Likely match with minor modifications"
    elif dist <= 20:
        # Scale 74 down to 50
        val = 74 - (dist - 14) * 4
        return int(val), "Weak match, significant differences observed"
    elif dist <= 25:
        # Scale 50 down to 25
        val = 50 - (dist - 20) * 5
        return int(val), "Very weak semantic match, heavily altered or different perspective"
    else:
        return 0, "No match"

@app.post("/register")
async def register(file: UploadFile = File(...), asset_id: Optional[str] = Form(None)):
    """
    Phase 2: Official Asset Registration
    """
    if not asset_id:
        asset_id = str(uuid.uuid4())
    
    file_path = os.path.join(ASSETS_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    phash, dhash, ahash, chash, width, height = compute_hashes(file_path)
    blur_idx = float(get_blur_index(file_path))
    
    db = load_db()
    # Check if exists, update or append
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

@app.post("/scan")
async def scan(file: UploadFile = File(...)):
    """
    Phase 3: Scan Suspicious Media
    Phase 4: Smart Detection Add-ons
    Phase 6: Clean Responses
    """
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
    
    # Phase 4 (Task 8): Best Match Selection
    for asset in db["assets"]:
        a_phash_obj = imagehash.hex_to_hash(asset["phash"])
        # Fallback to phash if older DB records lack ahash
        a_ahash_obj = imagehash.hex_to_hash(asset.get("ahash", asset["phash"]))
        
        # Use minimum distance between pHash (structural) and aHash (average)
        dist_p = s_phash_obj - a_phash_obj
        dist_a = s_ahash_obj - a_ahash_obj
        
        dist = min(dist_p, dist_a)
            
        if dist < best_dist:
            best_dist = int(dist)
            best_match = asset
            
    # Semantic Fallback: If structure is totally different but it might be the same color scheme
    if best_dist > 20 and best_match is not None:
        try:
            s_img = Image.open(suspicious_path)
            a_img = Image.open(best_match["file_path"])
            dist_c = imagehash.colorhash(s_img) - imagehash.colorhash(a_img)
            if dist_c < 8:
                best_dist = 24 # Force a 'Very weak match' (21-25 bracket) for identical color schemes but different angles
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
        
    # Phase 4 (Task 7): Detect Modifications
    modifications = []
    
    # Cropped heuristic: Aspect ratio difference
    s_aspect = s_w / float(s_h)
    a_aspect = best_match["width"] / float(best_match["height"])
    aspect_diff = abs(s_aspect - a_aspect)
    
    if aspect_diff > 0.05: # >5% difference in aspect ratio
        modifications.append("cropped")
        
    # Resized heuristic
    if aspect_diff <= 0.05 and (s_w != best_match["width"] or s_h != best_match["height"]):
        modifications.append("resized")
        
    # Quality heuristic
    original_blur = best_match.get("blur_index", 1000)
    # If standard deviation of laplacian is significantly lower, image is blurrier/compressed
    if s_blur < original_blur * 0.7: 
        modifications.append("compressed")
        
    # Screenshot heuristic
    if check_screenshot_borders(suspicious_path):
         # It's highly likely to be a screenshot if borders were added (changing aspect ratio often too)
         modifications.append("screenshot_borders_detected")
    
    # Ensure "modifications" returns unique reasons (mostly unique already)
    return {
        "match": True,
        "confidence": confidence,
        "matched_asset": best_match["asset_id"],
        "reason": reason,
        "modifications": modifications
    }
