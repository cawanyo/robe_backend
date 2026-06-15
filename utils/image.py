import httpx
async def fetch_and_process_image(image_url: str):
    # Open an async HTTP client
    async with httpx.AsyncClient() as client:
        response = await client.get(image_url)
        
        # Ensure the download was successful (e.g., not a 404 error)
        response.raise_for_status() 
        
        # Extract the raw binary data
        image_bytes = response.content 
        
    # Now you can pass it to any function expecting bytes
    # Example: await generate_image_embedding(image_bytes)
    return image_bytes
