from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

# Import your routers
from routers import pipeline, wardrobe, utility, clothe, credit, payment, outfit

app = FastAPI(title="Aura Wardrobe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# You can create a system.py and outfits.py router using the same pattern as above
# app.include_router(system.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(wardrobe.router, prefix="/api")
app.include_router(utility.router, prefix="/api")
app.include_router(clothe.router, prefix="/api")
app.include_router(credit.router, prefix="/api")
app.include_router(payment.router, prefix="/api")
app.include_router(outfit.router, prefix="/api")




# app.include_router(outfits.router, prefix="/api")