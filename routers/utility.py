import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from rembg import remove, new_session
import os

os.makedirs("./models", exist_ok=True)

# Force Hugging Face (CLIP) to save here permanently
os.environ["HF_HOME"] = "./models/huggingface"

# Force rembg (U2-Net) to save here permanently
os.environ["U2NET_HOME"] = "./models/u2net"


from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# If creating a new file, initialize the router like this:
router = APIRouter(tags=["Utilities"])

# clip_model = SentenceTransformer('clip-ViT-B-32')

rembg_session = new_session("u2net") # Explicitly load the bg removal model
print("Models loaded successfully!")


@router.post("/remove-background")
async def remove_image_background(file: UploadFile = File(...)):
    """
    Receives an image, strips the background using the U2-Net AI model, 
    and returns a clean, transparent PNG.
    """

    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

    try:
        # Read the raw image bytes from the mobile upload
        input_bytes = await file.read()
        
        # The rembg remove() function natively accepts bytes and outputs PNG bytes
        # It automatically detects the main subject (clothing) and makes the rest transparent
        output_bytes = remove(input_bytes, session=rembg_session)
        
        # Return the transparent image directly as a file response
        return Response(content=output_bytes, media_type="image/png")
        
    except Exception as e:
        logger.error(f"Background removal failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to process image background.")
    