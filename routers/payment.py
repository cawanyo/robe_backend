import stripe
from fastapi import APIRouter, Depends, Request, HTTPException
from dependencies import require_user
from config import STRIPE_SECRET_KEY
from services.supabase_client import pg_select, pg_delete, pg_rpc, sb_storage_delete, pg_insert, pg_update

# Import your dependencies: require_user, pg_insert

stripe.api_key = STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET = "whsec_YOUR_WEBHOOK_SECRET"

router = APIRouter()

# --- 1. Define your secure pricing tiers ---
PRICING_TIERS = {
    "tier_25": {"price_cents": 500, "credits": 25},   # 5 EUR
    "tier_50": {"price_cents": 1000, "credits": 50},  # 10 EUR
    "tier_100": {"price_cents": 1500, "credits": 100}, # 15 EUR
    "tier_250": {"price_cents": 3000, "credits": 250}, # 30 EUR
}

# --- 2. Create the Payment Intent ---
@router.post("/payments/create-intent")
async def create_payment_intent(tier_id: str, user: dict = Depends(require_user)):
    tier = PRICING_TIERS.get(tier_id)
    if not tier:
        raise HTTPException(status_code=400, detail="Invalid tier selected.")

    try:
        intent = stripe.PaymentIntent.create(
            amount=tier["price_cents"],
            currency="eur",
            metadata={
                "user_id": user["id"],
                "credits": tier["credits"],
                "tier_id": tier_id
            }
        )
        return {"client_secret": intent.client_secret}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- 3. The Secure Webhook (Credit Fulfillment) ---
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail="Webhook signature verification failed.")

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        user_id = intent["metadata"]["user_id"]
        credits_to_add = int(intent["metadata"]["credits"])

        # 🌟 SECURE FULFILLMENT: Add the credits to your Supabase ledger
        await pg_insert("credit_transactions", {
            "user_id": user_id,
            "amount": credits_to_add,
            "type": "PURCHASE",
            "description": f"Purchased {credits_to_add} credits pack"
        })

    return {"status": "success"}