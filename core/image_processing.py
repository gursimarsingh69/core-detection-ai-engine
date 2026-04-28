import cv2
import numpy as np
from PIL import Image
import imagehash

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
    
    # Heuristic: check if the first 5 rows and last 5 rows have extremely low variance
    top_var = np.var(gray[0:5, :])
    bottom_var = np.var(gray[-5:, :])
    left_var = np.var(gray[:, 0:5])
    right_var = np.var(gray[:, -5:])

    if (top_var < 10 and bottom_var < 10) or (left_var < 10 and right_var < 10):
        return True
    return False
