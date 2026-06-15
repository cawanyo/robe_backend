import io
from PIL import Image
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)
# Load the CLIP model into memory when your FastAPI app starts
# The 'clip-ViT-B-32' version is extremely fast, highly accurate, and lightweight
embedding_model = SentenceTransformer('clip-ViT-B-32')

async def generate_image_embedding(image_bytes: bytes) -> list[float]:
    """
    Takes raw image bytes, passes them through the CLIP AI model,
    and returns a 512-dimensional vector list.
    """
    try:
        # 1. Convert the raw bytes into a PIL Image object
        img = Image.open(io.BytesIO(image_bytes))
        
        # 2. Run the AI model to extract the visual features
        # We convert it to a standard Python list so it can be saved in Postgres/Supabase
        vector = embedding_model.encode(img).tolist()
        
        return vector
        
    except Exception as e:
        print(f"Failed to generate embedding: {e}")
        return []
    
    
async def generate_text_embedding(text: str) -> list[float]:
    """
    Takes a search query or description, passes it through the CLIP AI model,
    and returns a 512-dimensional vector list.
    """
    try:
        # 1. Strip any accidental whitespace from the user input
        clean_text = text.strip()
        
        # 2. Run the AI model to extract the semantic features
        # Notice we are passing a string instead of an image object
        vector = embedding_model.encode(clean_text).tolist()
        
        return vector
        
    except Exception as e:
        logger.error(f"Failed to generate text embedding: {e}")
        return []