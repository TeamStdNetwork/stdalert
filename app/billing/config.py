"""Billing-specific configuration."""
import os

STRIPE_API_KEY = os.getenv('STRIPE_API_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRO_MONTHLY_PRICE_ID = os.getenv('STRIPE_PRO_MONTHLY_PRICE_ID', 'price_xxx')
STRIPE_PRO_YEARLY_PRICE_ID = os.getenv('STRIPE_PRO_YEARLY_PRICE_ID', 'price_xxx')
STRIPE_TEAM_MONTHLY_PRICE_ID = os.getenv('STRIPE_TEAM_MONTHLY_PRICE_ID', 'price_xxx')
STRIPE_TEAM_YEARLY_PRICE_ID = os.getenv('STRIPE_TEAM_YEARLY_PRICE_ID', 'price_xxx')
