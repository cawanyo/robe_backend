import httpx
from fastapi import HTTPException
from config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, supabase_configured, logger

def sb_headers(user_jwt: str = None, service: bool = False) -> dict:
    key = SUPABASE_SERVICE_ROLE_KEY if service else SUPABASE_ANON_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {user_jwt or key}",
        "Content-Type": "application/json",
    }

async def sb_verify_user(jwt_token: str) -> dict:
    if not supabase_configured():
        raise HTTPException(503, "Supabase not configured on server")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {jwt_token}"},
        )
    if r.status_code != 200:
        raise HTTPException(401, "Invalid Supabase session")
    return r.json()

async def sb_storage_upload(bucket: str, path: str, content: bytes, content_type: str = "image/jpeg") -> str:
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            url,
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            content=content,
        )
    if r.status_code not in (200, 201):
        logger.error("storage upload failed %s %s", r.status_code, r.text)
        raise HTTPException(500, f"Storage upload failed: {r.text}")
    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"

async def sb_storage_delete(bucket: str, path: str) -> None:
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
    async with httpx.AsyncClient(timeout=30) as c:
        await c.delete(url, headers={"apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"})

async def pg_insert(table: str, row: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{SUPABASE_URL}/rest/v1/{table}", headers={**sb_headers(service=True), "Prefer": "return=representation"}, json=row)
    if r.status_code not in (200, 201):
        raise HTTPException(500, f"DB insert failed: {r.text}")
    data = r.json()
    return data[0] if isinstance(data, list) and data else data


async def pg_update(table: str, match: dict, update_data: dict) -> dict:
    """
    Updates existing rows in a Supabase table.
    :param table: The table name.
    :param match: Dictionary acting as the WHERE clause (e.g., {"id": "eq.123"}).
    :param update_data: Dictionary of the columns and new values to update.
    """
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.patch(
            f"{SUPABASE_URL}/rest/v1/{table}", 
            params=match, 
            headers={**sb_headers(service=True), "Prefer": "return=representation"}, 
            json=update_data
        )
        
    # Supabase returns 200 OK for successful updates with representation
    # and 204 No Content if returning representation is turned off
    if r.status_code not in (200, 204):
        raise HTTPException(500, f"DB update failed: {r.text}")
        
    data = r.json()
    return data[0] if isinstance(data, list) and data else data

async def pg_select(table: str, params: dict) -> list:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(service=True), params=params)
    if r.status_code != 200:
        raise HTTPException(500, f"DB select failed: {r.text}")
    return r.json()

async def pg_delete(table: str, params: dict) -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.delete(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(service=True), params=params)
    if r.status_code not in (200, 204):
        raise HTTPException(500, f"DB delete failed: {r.text}")

async def pg_rpc(fn: str, payload: dict) -> list:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{SUPABASE_URL}/rest/v1/rpc/{fn}", headers=sb_headers(service=True), json=payload)
    if r.status_code != 200:
        raise HTTPException(500, f"RPC failed: {r.text}")
    return r.json()