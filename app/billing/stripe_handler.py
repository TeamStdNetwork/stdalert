import logging
from typing import Dict, Any
import stripe

StripeError = getattr(stripe, "StripeError", Exception)
SignatureVerificationError = getattr(stripe, "SignatureVerificationError", Exception)

from app.billing.config import (
    STRIPE_PRO_MONTHLY_PRICE_ID,
    STRIPE_PRO_YEARLY_PRICE_ID,
    STRIPE_TEAM_MONTHLY_PRICE_ID,
    STRIPE_TEAM_YEARLY_PRICE_ID
)

logger = logging.getLogger(__name__)

class StripeHandler:
    """Handles Stripe interactions."""

    def __init__(self, api_key: str, webhook_secret: str) -> None:
        stripe.api_key = api_key
        self.webhook_secret = webhook_secret
        self.PRICE_IDS = {
            'pro_monthly': STRIPE_PRO_MONTHLY_PRICE_ID,
            'pro_yearly': STRIPE_PRO_YEARLY_PRICE_ID,
            'team_monthly': STRIPE_TEAM_MONTHLY_PRICE_ID,
            'team_yearly': STRIPE_TEAM_YEARLY_PRICE_ID
        }

    async def create_checkout_session(
        self,
        github_installation_id: int,
        tier: str,
        billing_period: str = 'monthly',
        success_url: str = '',
        cancel_url: str = ''
    ) -> Dict[str, Any]:
        """Creates a Stripe Checkout session for a subscription."""
        try:
            price_key = f"{tier}_{billing_period}"
            price_id = self.PRICE_IDS.get(price_key)
            if not price_id:
                raise ValueError(f"Invalid tier/period combination: {price_key}")

            session = stripe.checkout.Session.create(
                mode='subscription',
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                metadata={
                    'github_installation_id': github_installation_id,
                    'tier': tier
                },
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return {'session_id': session.id, 'checkout_url': session.url}
        except StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            raise

    async def create_customer_portal(self, customer_id: str, return_url: str) -> str:
        """Creates a billing portal session URL."""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            return session.url
        except StripeError as e:
            logger.error(f"Stripe error creating customer portal: {e}")
            raise

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Verifies and handles Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError as e:
            logger.error("Invalid payload in webhook")
            raise e
        except SignatureVerificationError as e:
            logger.error("Invalid signature in webhook")
            raise e

        # Handle events
        event_type = event['type']
        data = event['data']['object']
        
        return {'event_type': event_type, 'data': data}

    async def get_subscription_status(self, customer_id: str) -> Dict[str, Any]:
        """Gets the current subscription status for a customer."""
        try:
            subscriptions = stripe.Subscription.list(customer=customer_id, limit=1)
            if not subscriptions.data:
                return {'status': 'none', 'tier': 'free', 'current_period_end': 0, 'cancel_at_period_end': False}
            
            sub = subscriptions.data[0]
            tier_metadata = sub.get('metadata', {}).get('tier', 'free')
            
            return {
                'status': sub.status,
                'tier': tier_metadata,
                'current_period_end': sub.current_period_end,
                'cancel_at_period_end': sub.cancel_at_period_end
            }
        except StripeError as e:
            logger.error(f"Stripe error getting subscription status: {e}")
            raise

    async def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> bool:
        """Cancels a subscription."""
        try:
            if at_period_end:
                updated_sub = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
                return updated_sub.cancel_at_period_end
            else:
                deleted_sub = stripe.Subscription.delete(subscription_id)
                return deleted_sub.status == 'canceled'
        except StripeError as e:
            logger.error(f"Stripe error canceling subscription: {e}")
            raise
