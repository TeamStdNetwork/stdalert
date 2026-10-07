from enum import Enum
import logging

logger = logging.getLogger(__name__)

class PricingTier(Enum):
    FREE = 'free'
    PRO = 'pro'
    TEAM = 'team'
    ENTERPRISE = 'enterprise'

TIER_LIMITS = {
    PricingTier.FREE: {
        'max_repos': 3, 
        'scan_interval_hours': 48, 
        'features': ['dependency_scan', 'basic_security']
    },
    PricingTier.PRO: {
        'max_repos': 25, 
        'scan_interval_hours': 24, 
        'features': ['dependency_scan', 'security', 'secret_scan', 'license_check', 'code_review']
    },
    PricingTier.TEAM: {
        'max_repos': 100, 
        'scan_interval_hours': 12, 
        'features': ['all', 'dashboard', 'notifications', 'analytics']
    },
    PricingTier.ENTERPRISE: {
        'max_repos': -1, 
        'scan_interval_hours': 6, 
        'features': ['all', 'priority_support', 'custom_rules', 'sla']
    }
}

class PricingManager:
    def __init__(self):
        self._installation_tiers = {}

    def get_tier(self, installation_id: int) -> PricingTier:
        return self._installation_tiers.get(installation_id, PricingTier.FREE)
        
    def set_tier(self, installation_id: int, tier: PricingTier):
        self._installation_tiers[installation_id] = tier

    def check_limit(self, installation_id: int, feature: str) -> bool:
        tier = self.get_tier(installation_id)
        return self.can_use_feature(tier, feature)

    def get_repo_limit(self, tier: PricingTier) -> int:
        return TIER_LIMITS[tier]['max_repos']

    def can_use_feature(self, tier: PricingTier, feature: str) -> bool:
        features = TIER_LIMITS[tier]['features']
        if 'all' in features:
            return True
        return feature in features

    def get_scan_interval(self, tier: PricingTier) -> int:
        return TIER_LIMITS[tier]['scan_interval_hours']
