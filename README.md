# Media Alteration Detector 🕵️‍♂️

A high-performance, heuristically-driven FastAPI service designed to protect sports media copyright. It detects stolen, modified, or reposted official assets by using a robust blend of Perceptual Hashing (pHash) and Color Hashing (colorHash) to bypass simple modifications like cropping, resizing, quality dropping, or screenshotting.

## 🚀 Features

- **FastAPI Core**: Highly performant asynchronous backend with auto-generated Swagger documentation.
- **Structural Hashing (`pHash`)**: Detects exact layout matches, highly resilient against compression and minor resizing.
- **Semantic Color Fallback (`colorHash`)**: Intelligently identifies images that have been aggressively cropped, placed into a different aspect ratio, or screenshotted, by matching the color distribution palette.
- **Modification Heuristics**: Automatically attempts to reverse-engineer *how* a stolen image was modified (e.g. `["cropped", "compressed", "screenshot_borders_detected"]`).

---

## 🛠️ Installation & Setup

1. **Clone the repository** and navigate into the folder:
   ```bash
   cd detector
   ```

2. **Set up a Python Virtual Environment** (Optional but recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .\.venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the Server**:
   ```bash
   uvicorn main:app
   ```
   *(Note: Avoid using `--reload` when testing file uploads directly via Swagger, as file IO triggers ungraceful restarts).*

---

## 📖 API Endpoints

Once the server is running, you can access the interactive Swagger UI at **`http://127.0.0.1:8000/docs`**.

### `POST /register`
**Purpose**: Ingests an official asset to be protected.
**Process**: 
- Saves the file to `/assets`.
- Calculates its `pHash`, `aHash`, `colorHash`, and an initial Laplacian blur variance.
- Registers it into the local `db.json`.

### `POST /scan`
**Purpose**: Compares a suspicious/scraped image against the official database.
**Process**: 
- Generates fingerprints for the suspicious image.
- Compares structural hashes using Hamming Distance.
- Drops down to Semantic Color Fallback if structural geometry was heavily altered.
- **Returns**: A JSON payload with `match` (true/false), `confidence` (0-100%), the matched `asset_id`, and a list of `modifications` found.

---

## 🧩 Architecture Integration

This engine is designed to sit between a **Web Crawler** and a **UI Dashboard**.

1. **The Crawler**: Scrapes social media and sends downloaded images to the `/scan` endpoint.
2. **The Database**: When `/scan` returns `{"match": true}`, the crawler logs the hit (and the confidence score) into a central SQL/NoSQL database.
3. **The Dashboard**: A frontend React/Vue application pulls from the central database to show a visual feed of pirated/stolen media to the moderation team.
