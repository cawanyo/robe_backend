import json
import base64
import uuid
import asyncio
import logging
from openai import AsyncOpenAI
from config import OPENAI_API_KEY
from services.supabase_client import sb_storage_upload
from utils.embed import generate_image_embedding
# Import your supabase storage helper
# from services.supabase_client import sb_storage_upload_base64 
from config import UPLOADS_BUCKET
logger = logging.getLogger(__name__)
aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)

EXTRACTION_PROMPT = """You are a fashion analysis and product extraction system.
Analyze the input image and identify ALL clothing items visible on the person(s).

### TASK REQUIREMENTS
1. Detect and separate every clothing item visible.
2. For each item, provide a detailed structured description.

### OUTPUT FORMAT
You MUST return a valid JSON object with a single key "items" containing an array of objects.
Each object must have:
- category: [shirt, t-shirt, jeans, sneakers, bag, dress, pants, shorts, skirt, jacket, coat, sweater, shoes, boots, hat, other]
- primary_color: string
- secondary_color: string
- style: [casual, formal, streetwear, sporty, vintage, minimalist, bohemian, business, evening]
- material: [cotton, denim, leather, wool, polyester, linen, silk, knit, synthetic, other]
- description: string an consice description of the item, including unique features.
- prompt: A highly detailed image generation prompt describing the item in a way that can be used for image generation. The result should be the exact item, with all the necessary details, be specific as possible, describing every subtly in the item.  Use clean studio product photography style, plain white background, soft lighting, high detail fabric realism, NO model, NO human body, isolated garment only.
"""

SYSTEM_OUTFIT_PROMPT = """
        You are an elite personal stylist. Given a user's prompt and a JSON list of their available clothing items, curate the perfect 3-to-5 piece outfit.
        Return ONLY valid JSON with this exact structure:
        [
            {
            "title": "Short catchy name for the look",
            "prompt": "the prompt to generate the image what the complete outfit will look like"
            "reasoning": "1-2 sentences explaining why these pieces work together.",
            "selected_items": [
                { "id": "uuid-here", "layer": "BASE_TOP" },
                { "id": "uuid-here", "layer": "BOTTOM" },
                { "id": "uuid-here", "layer": "OUTERWEAR" },
                { "id": "uuid-here", "layer": "FOOTWEAR" }
            ]
            }
        ]
        Valid layers: BASE_TOP, BOTTOM, OUTERWEAR, FOOTWEAR, ACCESSORY.
        """

async def analyze_wardrobe_image(image_url: str) -> list:
    """Sends the image to GPT-4o to extract JSON details and generation prompts."""
    try:
        response = await aclient.chat.completions.create(
            model="gpt-4o", # Best model for vision tasks
            response_format={"type": "json_object"}, # Forces strict JSON output
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]
        )
        
        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        logger.info(f"Extracted items from image: {data.get('items', [])}")
        return data.get("items", [])
    except Exception as e:
        logger.error(f"Failed to analyze image: {e}")
        return []

async def generate_and_save_garment(item_data: dict, user_id: str) -> dict:
    """Generates the isolated image and uploads it to Supabase."""
    try:
        # 1. Generate the isolated image using DALL-E 3 (or preferred model)
        result = await aclient.images.generate(
            model="gpt-image-1", 
            prompt=item_data["prompt"],
        )
        image_b64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_b64)
        
        # 2. Upload directly to Supabase
        filename = f"{user_id}/{uuid.uuid4().hex}.png"
        
        path = f"{user_id}/{uuid.uuid4().hex}.jpg"
        public_url = await sb_storage_upload(UPLOADS_BUCKET, path, image_bytes)
        
        embedding_vector = await generate_image_embedding(image_bytes)
        # 3. Format the final item for your database
        return {
            "image_url": public_url,
            "category": item_data.get("category"),
            "primary_color": item_data.get("primary_color"),
            "style": item_data.get("style"),
            "material": item_data.get("material"),
            "description": item_data.get("description"),
            "status": "success",
            "embedding": embedding_vector
        }
    except Exception as e:
        logger.error(f"Failed to generate image for {item_data.get('category')}: {e}")
        return {"category": item_data.get("category"), "status": "error", "error": str(e)}
    
async def generate_outit(prompt, candidate_items, user_id):
    try:
        llm_message = f"Prompt: {prompt}\n\nAvailable Wardrobe:\n{json.dumps(candidate_items)}"
        
        response = await aclient.chat.completions.create(
            model="gpt-4o", # Best model for vision tasks
            response_format={"type": "json_object"}, # Forces strict JSON output
            messages=[
                {"role": "system", "content": SYSTEM_OUTFIT_PROMPT},
                {"role": "user", "content": llm_message}
            ],
        )
        logger.info(response)
        outfit_data = json.loads(response.choices[0].message.content)
        
        
        
        result = await aclient.images.generate(
            model="gpt-image-1", 
            prompt=outfit_data["prompt"],
        )
        image_b64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_b64)
        
        # 2. Upload directly to Supabase
        filename = f"{user_id}/{uuid.uuid4().hex}.png"
        
        path = f"{user_id}/{uuid.uuid4().hex}.jpg"
        public_url = await sb_storage_upload(UPLOADS_BUCKET, path, image_bytes)
        
        output = outfit_data
        output["outfit_url"] = public_url
        logger.info(output)
        return output
    except Exception as e: 
         logger.error(f"Failed to generate outfit: {e}")