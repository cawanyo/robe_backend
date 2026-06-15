from pydantic import BaseModel, Field
from typing import List, Optional

class UploadIn(BaseModel):
    image_path: str 
    image_public_url: str

class UploadImageIn(BaseModel):
    filename: str = Field(default="photo.jpg", max_length=160)
    content_type: str = Field(default="image/jpeg", max_length=80)
    data_base64: str

class AnalyseImageIn(BaseModel):
    image_url : str
    
class ExtractImageIn(BaseModel):
    detected_items: List[dict]
    source_url: str
    
    
class BatchUploadIn(BaseModel):
    photos: List[UploadIn]

class SearchIn(BaseModel):
    query: str

class OutfitsIn(BaseModel):
    seed_item_id: Optional[str] = None
    occasion: Optional[str] = None