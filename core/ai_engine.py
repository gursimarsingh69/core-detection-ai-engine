import os
import json
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY")

def verify_semantic_match_with_gemini(suspicious_path, db_assets):
    """
    Uses Gemini Multimodal API to compare the suspicious image against a batch of official assets.
    db_assets: List of dicts representing registered assets.
    """
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        return None  # Skip if API key not set

    try:
        # Initialize client using the new google.genai SDK
        client = genai.Client(api_key=API_KEY)
        
        prompt = """
        You are an expert copyright and media alteration detection AI.
        I will provide you with a Suspicious Image, followed by a list of Official Registered Images.
        Does the Suspicious Image depict the EXACT SAME real-world event, scene, or person at the exact same moment in time as any of the Official Images? It might be taken from a different angle, have different lighting, or be heavily cropped.
        
        Respond strictly in the following JSON format without any markdown wrappers or extra text:
        {
          "match": true,
          "similarity_score": <integer 0-100 representing how semantically similar the most similar official image is>,
          "matched_asset_id": "<asset_id of the most similar official image, MUST NOT BE NULL>",
          "reason": "<brief explanation>",
          "modifications": ["<list of visual differences, e.g. 'cropped', 'different lighting', or 'none'>"]
        }
        """
        
        contents = [prompt]
        
        # Load suspicious image
        susp_img = Image.open(suspicious_path)
        contents.append("Suspicious Image:")
        contents.append(susp_img)
        
        contents.append("Official Images:")
        for asset in db_assets:
            try:
                img = Image.open(asset["file_path"])
                contents.append(f"Asset ID: {asset['asset_id']}")
                contents.append(img)
            except Exception:
                pass
                
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        if not response.candidates or not response.candidates[0].content.parts:
            print("Gemini API Error: Empty response parts. Finish reason:", response.candidates[0].finish_reason if response.candidates else "Unknown")
            return None
            
        text = response.candidates[0].content.parts[0].text.strip()
        
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
            
        result = json.loads(text)
        return result
    except Exception as e:
        print("Gemini API Error:", e)
        return None
