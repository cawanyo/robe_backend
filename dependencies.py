from fastapi import Header, HTTPException
from typing import Optional
from services.supabase_client import sb_verify_user

async def require_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    user = await sb_verify_user(token)
    user["_jwt"] = token
    return user