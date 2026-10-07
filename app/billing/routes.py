import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
import stripe

SignatureVerificationError = getattr(stripe, "SignatureVerificationError", Exception)

from app.billing.stripe_handler import StripeHandler
from app.billing.subscription_manager import SubscriptionManager
from app.billing.config import STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

stripe_handler = StripeHandler(api_key=STRIPE_API_KEY, webhook_secret=STRIPE_WEBHOOK_SECRET)
subscription_manager = SubscriptionManager()

class CheckoutRequest(BaseModel):
    installation_id: int
    tier: str
    billing_period: str = 'monthly'

@router.post("/checkout")
async def create_checkout(req: CheckoutRequest):
    """Creates a Stripe checkout session."""
    try:
        # success/cancel urls would be configured properly in reality
        result = await stripe_handler.create_checkout_session(
            github_installation_id=req.installation_id,
            tier=req.tier,
            billing_period=req.billing_period,
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel'
        )
        return {"checkout_url": result['checkout_url']}
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handles Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing signature")

    try:
        event = await stripe_handler.handle_webhook(payload, sig_header)
        event_type = event['event_type']
        data = event['data']

        if event_type == 'checkout.session.completed':
            # Activate subscription
            metadata = data.get('metadata', {})
            installation_id = int(metadata.get('github_installation_id', 0))
            tier = metadata.get('tier', 'free')
            customer_id = data.get('customer')
            subscription_id = data.get('subscription')
            
            if installation_id:
                await subscription_manager.activate(
                    installation_id=installation_id,
                    tier=tier,
                    customer_id=customer_id,
                    subscription_id=subscription_id
                )
                
        elif event_type == 'customer.subscription.updated':
            # Could update tier here if plan changed
            customer_id = data.get('customer')
            # simplified handling
            pass
            
        elif event_type == 'customer.subscription.deleted':
            # Downgrade to free
            # simplified handling, would need to map customer_id to installation_id
            pass
            
        elif event_type == 'invoice.payment_failed':
            logger.warning(f"Payment failed for customer {data.get('customer')}")

        return {"status": "success"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/portal/{installation_id}")
async def get_portal(installation_id: int):
    """Creates a customer portal session."""
    sub = await subscription_manager.get_subscription(installation_id)
    if not sub or not sub.get('customer_id'):
        raise HTTPException(status_code=404, detail="No active subscription found")
        
    try:
        url = await stripe_handler.create_customer_portal(
            customer_id=sub['customer_id'],
            return_url='https://example.com/account'
        )
        return {"portal_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{installation_id}")
async def get_status(installation_id: int):
    """Gets subscription status."""
    sub = await subscription_manager.get_subscription(installation_id)
    tier = sub.get('tier', 'free') if sub else 'free'
    status = sub.get('status', 'none') if sub else 'none'
    
    # Feature mapping based on tier
    features = []
    if tier == 'pro':
        features = ['feature1', 'feature2']
    elif tier == 'team':
        features = ['feature1', 'feature2', 'feature3']
        
    return {
        "tier": tier,
        "status": status,
        "features": features,
        "limits": {"projects": 10 if tier == 'pro' else 1 if tier == 'free' else -1}
    }
