import os
import json
from config import DB_FILE

def load_db():
    if not os.path.exists(DB_FILE):
        return {"assets": []}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"assets": []}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)
