
from fastapi import APIRouter, Depends, HTTPException
from dependencies import require_user
from schemas import SearchIn
from config import GARMENTS_BUCKET, logger
from services.supabase_client import pg_select, pg_delete, pg_rpc, sb_storage_delete, pg_insert, pg_update
from utils.image import fetch_and_process_image



from typing import Optional
router = APIRouter(tags=["Wardrobe"])
from pydantic import BaseModel

from utils.embed import generate_image_embedding
from routers.pipeline import download_bytes


class ManualItemIn(BaseModel):
    image_url: str
    category: str
    subcategory: Optional[str] = None
    style: Optional[str] = None
    material: Optional[str] = None
    primary_color: Optional[str] = None
    description: Optional[str] = None


class ClothingItemUpdate(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    style: Optional[str] = None
    material: Optional[str] = None
    primary_color: Optional[str] = None
    description: Optional[str] = None
    favorite: Optional[bool] = None
    image_url: Optional[str] = None


@router.get("/clothes")
async def list_clothes(user: dict = Depends(require_user)):
    items = await pg_select("clothing_items", {"user_id": f"eq.{user['id']}", "select": "*", "order": "created_at.desc"})
    return {"items": items}

@router.get("/clothes/{item_id}")
async def delete_clothes(item_id: str, user: dict = Depends(require_user)):
    items = await pg_select("clothing_items", {"id": f"eq.{item_id}", "user_id": f"eq.{user['id']}", "select": "*"})
    if not items:
        raise HTTPException(404, "Not found")
  
    return items[0]

@router.delete("/clothes/{item_id}")
async def delete_clothes(item_id: str, user: dict = Depends(require_user)):
    items = await pg_select("clothing_items", {"id": f"eq.{item_id}", "user_id": f"eq.{user['id']}", "select": "image_url"})
    if not items:
        raise HTTPException(404, "Not found")
    try:
        key = items[0]["image_url"].split(f"/storage/v1/object/public/{GARMENTS_BUCKET}/", 1)[1]
        await sb_storage_delete(GARMENTS_BUCKET, key)
    except Exception:
        pass
    await pg_delete("clothing_items", {"id": f"eq.{item_id}", "user_id": f"eq.{user['id']}"})
    return {"ok": True}



@router.post("/clothes/insert")
async def create_manual_clothes(body: ManualItemIn, user: dict = Depends(require_user)):
    # 1. Optionally generate an HF embedding here for semantic search if you want!
    # embedding = await hf_image_embedding()
   
    embedding_vector = await generate_image_embedding(await fetch_and_process_image(body.image_url))
    # 2. Save to Supabase
    row = {
        "user_id": user["id"],
        "image_url": body.image_url,
        "category": body.category,
        'subcategory': body.subcategory,
        "style": body.style,
        "material": body.material,
        "primary_color": body.primary_color,
        "description": body.description,
        "embedding": embedding_vector
    }
    inserted = await pg_insert("clothing_items", row)
    return inserted


@router.get("/clothes/{id}/similar")
async def get_related_items(id: str, user: dict = Depends(require_user)):
    """
    Finds visually similar items in the user's wardrobe by comparing 
    the current item's embedding against all others.
    """
    # 1. Fetch the target item from the database to get its vector embedding
    source_items = await pg_select("clothing_items", {
        "id": f"eq.{id}", 
        "user_id": f"eq.{user['id']}"
    })
    
    if not source_items:
        raise HTTPException(status_code=404, detail="Item not found")
        
    source_item = source_items[0]
    target_embedding = source_item.get("embedding")
    
    # If the item was created before you added AI embeddings, return an empty list
    if not target_embedding:
        return {"items": []}

    try:
        # 2. Use your existing pgvector RPC function to find matches!
        # We request a slightly higher count (e.g., 6) because the RPC will likely 
        # return the source item itself as a 100% match.
        results = await pg_rpc("match_clothing", {
            "query_embedding": target_embedding, 
            "match_user": user["id"], 
            "match_count": 6
        })
        
        # 3. Filter out the original item so it doesn't show up in its own "Similar" list
        filtered_results = [item for item in results if item["id"] != id]
        
        # Return the top 5 closest matches
        return {"items": filtered_results[:5]}
        
    except Exception as e:
        # Fallback if the RPC fails (just like your search endpoint)
        print(f"Error fetching related items: {e}")
        return {"items": []}
    
    
    


# 2. The Endpoint
@router.patch("/clothes/{item_id}")
async def update_clothing_item(
    item_id: str, 
    body: ClothingItemUpdate, 
    user: dict = Depends(require_user)
):
    """Updates a specific garment in the authenticated user's wardrobe."""
    
    # exclude_unset=True ensures we only update fields the user actually sent
    update_data = body.dict(exclude_unset=True)
    
    if not update_data:
        return {"status": "success", "message": "No changes provided."}

    try:
        # CRITICAL: We pass BOTH the item's id and the user's id to the query dictionary.
        # This prevents a user from guessing an item ID and modifying someone else's clothes.
        await pg_update(
            "clothing_items", 
            {
                "id": f"eq.{item_id}",
                "user_id": f"eq.{user['id']}"
            }, 
            update_data
        )
        
        return {"status": "success", "message": "Garment updated successfully"}
        
    except Exception as e:
        print(f"Update clothing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update garment.")




