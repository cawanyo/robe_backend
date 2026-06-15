from fastapi import APIRouter, Depends, HTTPException
from dependencies import require_user
from schemas import SearchIn
from config import GARMENTS_BUCKET, logger
from services.supabase_client import pg_select, pg_delete, pg_rpc, sb_storage_delete, pg_insert

from utils.embed import generate_text_embedding
router = APIRouter(tags=["Wardrobe"])



   
@router.post("/search")
async def search(body: SearchIn, user: dict = Depends(require_user)):
    if not body.query.strip():
        return {"items": []}
    embedding = await generate_text_embedding(body.query.strip())
    try:
        results = await pg_rpc("match_clothing", {"query_embedding": embedding, "match_user": user["id"], "match_count": 24})
    except HTTPException as e:
        results = await pg_select("clothing_items", {"user_id": f"eq.{user['id']}", "limit": "24"})
    return {"items": results}
    return {}




