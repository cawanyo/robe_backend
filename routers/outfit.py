import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI
# Import your require_user, supabase client, and pg_insert here
from services.supabase_client import pg_select, pg_delete, pg_rpc, sb_storage_delete, pg_insert, pg_update
from dependencies import require_user
from utils.embed import generate_text_embedding
import logging
from services.ai_client import generate_outit

from typing import List, Optional
# Import your require_user and pg_insert

router = APIRouter()

class CustomCanvasItem(BaseModel):
    id: str
    zIndex: int
    pos_x: float
    pos_y: float
    scale: float

class SaveCustomOutfitRequest(BaseModel):
    title: str = "Studio Creation"  # Default title if the user doesn't name it
    items: List[CustomCanvasItem]
router = APIRouter()


class OutfitRequest(BaseModel):
    prompt: str  # e.g., "A smart casual outfit for a 16°C rainy day in Paris"

@router.get("/outfits")
async def get_outfits(user: dict = Depends(require_user)):
    logging.info(user)
    outfits = await pg_select(
        "outfits", 
        {
            "user_id": f"eq.{user['id']}", 
            "select": "*", 
            "order": "created_at.desc"
        }
    )
     
    return outfits

import logging
from fastapi import APIRouter, Depends, HTTPException

@router.get("/outfits/{outfit_id}")
async def get_outfit(outfit_id: str, user: dict = Depends(require_user)):
    
    # 1. Fetch the master outfit record
    outfits = await pg_select(
        "outfits", 
        {
            "id": f"eq.{outfit_id}",
            "user_id": f"eq.{user['id']}", 
            "select": "*"
        }
    )
    
    # 2. EARLY EXIT: Check if it exists BEFORE making more database calls
    if not outfits:
        raise HTTPException(status_code=404, detail="Outfit not found")
        
    outfit_data = outfits[0]
    
    # 3. Fetch the bridge table records (outfit_items)
    outfits_items = await pg_select(
        "outfit_items", 
        {
            "outfit_id": f"eq.{outfit_id}",
            "select": "*"
        }
    )
    
    # 4. Fetch actual clothing details efficiently and attach them
    if outfits_items:
        # Extract all the clothing IDs into a simple list
        clothing_ids = [str(item['clothing_item_id']) for item in outfits_items]
        
        # Create a comma-separated string for the SQL 'IN' clause (e.g., "id1,id2,id3")
        ids_string = ",".join(clothing_ids)
        
        # Make ONE single database call to get all clothing items at once
        clothes = await pg_select(
            "clothing_items", 
            {
                "id": f"in.({ids_string})",
                "select": "*"
            }
        )
        
        # To make merging easy, create a dictionary of clothes keyed by their ID
        clothes_lookup = {clothe['id']: clothe for clothe in clothes}
        
        final_items = []
        for bridge_item in outfits_items:
            clothe_id = bridge_item['clothing_item_id']
            if clothe_id in clothes_lookup:
                # Merge the clothing data with the bridge data (layer, z_index, position, etc.)
                merged_item = {
                    **clothes_lookup[clothe_id],
                    "layer_type": bridge_item.get("layer_type"),
                    "z_index": bridge_item.get("z_index", 1),
                    "pos_x": bridge_item.get("pos_x", 0),
                    "pos_y": bridge_item.get("pos_y", 0),
                    "scale": bridge_item.get("scale", 1)
                }
                final_items.append(merged_item)
                
        # Attach the fully constructed items array to the outfit object
        outfit_data["items"] = final_items
    else:
        # If there are no items in the bridge table, return an empty array
        outfit_data["items"] = []
        
    # 5. Return the complete package to React Native
    return outfit_data
    
@router.post("/outfits/generate")
async def generate_ai_outfit(req: OutfitRequest, user: dict = Depends(require_user)):
    try:
        # --- 1. Vectorize the User's Prompt ---
        # embedding_res = await openai_client.embeddings.create(
        #     input=req.prompt,
        #     model="text-embedding-3-small"
        # )
        # query_vector = embedding_res.data[0].embedding
        query_vector = await generate_text_embedding(req.prompt)

        # --- 2. Semantic Search via Supabase RPC ---
        # Fetch the top 30 most relevant items from their 1000+ item wardrobe
        rpc_response = await pg_rpc(
            "match_wardrobe_items",
            {
                "query_embedding": query_vector,
                "match_threshold": 0.2, # Adjust this sensitivity as needed
                "match_count": 30,
                "p_user_id": user["id"]
            }
        )
        candidate_items = rpc_response
        if not candidate_items or len(candidate_items) < 3:
            raise HTTPException(status_code=400, detail="Not enough matching items found.")

        
        # --- 3. The LLM Stylist (Structured JSON Output) ---
        

        

        # outfit_data = await generate_outit(prompt=req.prompt, candidate_items=candidate_items, user_id=user['id'])
        outfit_data = {'id': '1ff5292f-3acd-4706-b546-2385596f5e3e', 'user_id': 'ef935ca5-6bda-44d6-afb5-89e0d3c3cbfb', 'title': 'Sunny Sophistication', 'reasoning': "This look centers around the elegant yellow evening gown that sets a sophisticated base. Paired with a simple yellow accessory, it keeps the ensemble light and cohesive, while muted footwear doesn't distract from the vividness of the yellow.", 'created_at': '2026-06-14T19:50:23.198191+00:00', 'outfit_url': 'https://qtfzcwykujtjlkymecvv.supabase.co/storage/v1/object/public/uploads/ef935ca5-6bda-44d6-afb5-89e0d3c3cbfb/2883fcc73c7f4ab6ba331c7d48ade7c4.jpg'}

        
        # --- 4. Save to Database ---
        # Save the master outfit
        new_outfit = await pg_insert("outfits", {
            "user_id": user["id"],
            "title": outfit_data["title"],
            "reasoning": outfit_data["reasoning"],
            "outfit_url": outfit_data["outfit_url"]
        })
        
        logging.info(new_outfit)
    
        outfit_id = new_outfit["id"]

        
        # Save the bridge items
        outfit_items_payload = [
            {
                "outfit_id": outfit_id,
                "clothing_item_id": item["id"],
                "layer_type": item["layer"]
            }
            for item in outfit_data["selected_items"]
        ]
        
        # Assuming you have a bulk insert function, or loop through pg_insert
        for payload in outfit_items_payload:
            await pg_insert("outfit_items", payload)

        return {
            "outfit_id": outfit_id,
            "title": outfit_data["title"],
            "reasoning": outfit_data["reasoning"],
            "selected_items": outfit_data["selected_items"],
            "outfit_url": outfit_data["outfit_url"]
        }

    except Exception as e:
        print("Outfit Generation Error:", e)
        raise HTTPException(status_code=500, detail="Failed to generate outfit.")
    
    





@router.post("/outfits/custom")
async def save_custom_outfit(req: SaveCustomOutfitRequest, user: dict = Depends(require_user)):
    try:
        if not req.items:
            raise HTTPException(status_code=400, detail="Cannot save an empty outfit.")

        # 1. Create the master Outfit record
        new_outfit = await pg_insert("outfits", {
            "user_id": user["id"],
            "title": req.title,
            "reasoning": "Custom look curated in the Studio.", # Default reasoning
            "is_custom": True
        })
        outfit_id = new_outfit["id"]

        # 2. Prepare the bridge table payload
        outfit_items_payload = [
            {
                "outfit_id": outfit_id,
                "clothing_item_id": item.id,
                "z_index": item.zIndex,
                "pos_x": item.pos_x,
                "pos_y": item.pos_y,
                "scale": item.scale,
                "layer_type": "CUSTOM"
            }
            for item in req.items
        ]
        
        # 3. Save all items to the bridge table
        for payload in outfit_items_payload:
            await pg_insert("outfit_items", payload)

        return {
            "success": True,
            "outfit_id": outfit_id,
            "message": "Outfit saved successfully."
        }

    except Exception as e:
        print("Save Custom Outfit Error:", e)
        raise HTTPException(status_code=500, detail="Failed to save custom outfit.")