from fastapi import APIRouter, Depends, HTTPException
# Import your require_user and pg_select dependencies here
from typing import Optional
from dependencies import require_user
from services.supabase_client import pg_select, pg_delete, pg_rpc, sb_storage_delete, pg_insert, pg_update

router = APIRouter(tags=["Wardrobe"])
from pydantic import BaseModel


@router.get("/credits/history")
async def get_credit_history(user: dict = Depends(require_user)):
    # Fetch the ledger for this user
    transactions = await pg_select(
        "credit_transactions", 
        {
            "user_id": f"eq.{user['id']}", 
            "select": "*", 
            "order": "created_at.desc"
        }
    )
    
    # Calculate the current balance based on the ledger
    # Note: If your ledger gets massive, you may want to cache this balance on the users table,
    # but calculating it on the fly guarantees 100% accuracy.
    balance = sum(tx.get('amount', 0) for tx in transactions)
    
    return {
        "balance": balance,
        "transactions": transactions
    }
    
    
    
    