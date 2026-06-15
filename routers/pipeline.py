import uuid
import base64
import asyncio
import httpx
from io import BytesIO
from PIL import Image
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from dependencies import require_user
from schemas import UploadIn, UploadImageIn, BatchUploadIn, AnalyseImageIn, ExtractImageIn
from config import UPLOADS_BUCKET, GARMENTS_BUCKET, logger
from services.supabase_client import sb_storage_upload, pg_insert, pg_rpc, pg_select, pg_update
from openai import OpenAI
import base64
import mimetypes
from services.ai_client import analyze_wardrobe_image, generate_and_save_garment
from pydantic import BaseModel
router = APIRouter(tags=["Pipeline"])




    
async def download_bytes(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(url)
    if r.status_code != 200:
        raise HTTPException(400, f"Could not download {url}")
    return r.content




# -------------------------------------------------------------------------
# Core Async Pipeline Handler (Scenario C)
# -------------------------------------------------------------------------

@router.post('/image/analyse')
async def analyze_image(body: AnalyseImageIn, user: dict = Depends(require_user)):
    """Analyzes a single wardrobe image and returns detected items."""
    
    detected_items = await analyze_wardrobe_image(body.image_url)
    if not detected_items:
        return { "items": []}
    
    return {"items": detected_items}

@router.post('/image/extract')
async def extract_image(body: ExtractImageIn, user: dict = Depends(require_user)):
    """Analyzes a single wardrobe image and returns detected items."""
    
    tasks = [generate_and_save_garment(item, user["id"]) for item in body.detected_items]
    
    
    processed_results = await asyncio.gather(*tasks)
    
    successful_items = []
    for item in processed_results:
        if item.get("status") == "success":
            # Clean up the status key before saving
            row = {
                "user_id": user["id"],
                "image_url": item.get("image_url"),
                "source_url": body.source_url,
                "category": item.get("category"),
                "primary_color": item.get("primary_color"),
                "style": item.get("style"),
                "material": item.get("material"),
                "description": item.get("description"),
                "embedding": item.get("embedding"),
            }
            # Save to Postgres via Supabase
            await pg_insert("clothing_items", row)
            # await pg_rpc("deduct_user_credit", {"user_id": user["id"]})
            successful_items.append(item)

    return  {"items": successful_items, "count": len(successful_items)}

async def _process_single_photo(user_id: str, image_public_url: str) -> List[dict]:
    
    detected_items = await analyze_wardrobe_image(image_public_url)
    if not detected_items:
        raise HTTPException(status_code=400, detail="No items detected in the image.")
    
    tasks = [generate_and_save_garment(item, user_id) for item in detected_items]
    
    processed_results = await asyncio.gather(*tasks)
    
    successful_items = []
    for item in processed_results:
        if item.get("status") == "success":
            # Clean up the status key before saving
            row = {
                "user_id": user_id,
                "image_url": item.get("image_url"),
                "source_url": image_public_url,
                "category": item.get("category"),
                "primary_color": item.get("primary_color"),
                "style": item.get("style"),
                "material": item.get("material"),
                "description": item.get("description"),
                "embedding": item.get("embedding"),
            }
            # Save to Postgres via Supabase
            await pg_insert("clothing_items", row)
            await pg_rpc("deduct_user_credit", {"user_id": user_id})
            successful_items.append(item)

    return  successful_items




@router.post("/uploads/image")
async def upload_image(body: UploadImageIn, user: dict = Depends(require_user)):
    image_bytes = base64.b64decode(body.data_base64, validate=True)
    path = f"{user['id']}/{uuid.uuid4().hex}.jpg"
    public_url = await sb_storage_upload(UPLOADS_BUCKET, path, image_bytes, body.content_type)
    return {"image_path": path, "image_public_url": public_url}



@router.post("/clothes/batch_upload")
async def batch_upload(body: BatchUploadIn, user: dict = Depends(require_user)):
    """Process several photos concurrently. Returns per-photo results."""
    profile = await pg_select("profiles", {"id": f"eq.{user['id']}"})
    if not profile or profile[0].get("credits", 0) < 1:
        raise HTTPException(status_code=402, detail="Not enough credits. Please recharge your account.")
    if not body.photos:
        return {"photos": [], "total_items": 0}
    if len(body.photos) > 10:
        raise HTTPException(400, "Max 10 photos per batch")

    async def safe_one(p: UploadIn):
        try:
            items = await _process_single_photo(user["id"], p.image_public_url)
            # return {"image_path": p.image_path, "ok": True, "items": items, "count": len(items)}
            return {"image_path": p.image_path, "ok": True, "items": items, "count": len(items)}  
        except Exception as e:
            logger.exception("batch photo failed: %s", e)
            print(e)
            return {"image_path": p.image_path, "ok": False, "error": str(e), "items": [], "count": 0}

    results = await asyncio.gather(*[safe_one(p) for p in body.photos])
    total = sum(r["count"] for r in results)
    return {"photos": results, "total_items": total}



@router.post("/clothes/upload")
async def upload_pipeline(body: UploadIn, user: dict = Depends(require_user)):
    saved = await _process_single_photo(user["id"], body.image_public_url)
    return {"count": len(saved), "items": saved}


@router.get("/user/profile")
async def get_user_profile(user: dict = Depends(require_user)):
    """Fetches the user's current profile and credit balance."""
    profile = await pg_select("profiles", {"id": f"eq.{user['id']}"})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile[0]



class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    description: Optional[str] = None
    preferred_style: Optional[str] = None
    gender: Optional[str] = None
    avatar_url: Optional[str] = None

@router.put("/user/profile")
async def update_user_profile(body: ProfileUpdate, user: dict = Depends(require_user)):
    """Updates the authenticated user's profile information."""
    
    # exclude_unset=True ensures we only update fields the user actually sent
    update_data = body.dict(exclude_unset=True)
    
    if not update_data:
        return {"status": "success", "message": "No changes provided."}
    logger.info("Updating profile for user %s with data: %s", user['id'], update_data)
    try:
        # Assuming you have a pg_update helper similar to pg_select
        # Or direct Supabase client: supabase.table('profiles').update(update_data).eq('id', user['id']).execute()
        await pg_update("profiles", {"id": f"eq.{user['id']}"}, update_data)
        
        return {"status": "success", "message": "Profile updated successfully"}
    except Exception as e:
        # This will catch errors like someone trying to claim a username that is already taken
        if "unique constraint" in str(e).lower() and "username" in str(e).lower():
            raise HTTPException(status_code=400, detail="That username is already taken.")
        raise HTTPException(status_code=500, detail="Failed to update profile.")
    
    
    

@router.get("/user/check-username")
async def check_username(username: str):
    """Checks if a username is already taken by another user."""
    try:
        # Check if any profile has this exact username
        existing_user = await pg_select("profiles", {"username": f"eq.{username}"})
        
        # If the list is empty, the username is available
        is_available = len(existing_user) == 0
        return {"available": is_available}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to verify username.")
    
    


