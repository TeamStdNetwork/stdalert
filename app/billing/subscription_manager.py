import json
import os
import asyncio
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class SubscriptionManager:
    """Manages subscription state using a JSON file."""

    def __init__(self, data_file: str = "data/subscriptions.json"):
        self.data_file = data_file
        self._lock = asyncio.Lock()
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w') as f:
                json.dump({}, f)

    async def _read_data(self) -> Dict[str, Any]:
        async with self._lock:
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to read subscription data: {e}")
                return {}

    async def _write_data(self, data: Dict[str, Any]):
        async with self._lock:
            try:
                with open(self.data_file, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to write subscription data: {e}")

    async def activate(self, installation_id: int, tier: str, customer_id: str, subscription_id: str):
        """Activates a subscription for an installation."""
        data = await self._read_data()
        data[str(installation_id)] = {
            'tier': tier,
            'customer_id': customer_id,
            'subscription_id': subscription_id,
            'status': 'active'
        }
        await self._write_data(data)

    async def deactivate(self, installation_id: int):
        """Deactivates a subscription, downgrading to free tier."""
        data = await self._read_data()
        inst_id_str = str(installation_id)
        if inst_id_str in data:
            data[inst_id_str]['tier'] = 'free'
            data[inst_id_str]['status'] = 'canceled'
            await self._write_data(data)

    async def get_tier(self, installation_id: int) -> str:
        """Gets the current tier for an installation."""
        data = await self._read_data()
        inst_data = data.get(str(installation_id), {})
        return inst_data.get('tier', 'free')

    async def get_subscription(self, installation_id: int) -> Optional[Dict[str, Any]]:
        """Gets the full subscription details for an installation."""
        data = await self._read_data()
        return data.get(str(installation_id))

    async def list_all(self) -> List[Dict[str, Any]]:
        """Lists all subscriptions."""
        data = await self._read_data()
        return [{'installation_id': int(k), **v} for k, v in data.items()]

    async def update_tier(self, installation_id: int, tier: str):
        """Updates the tier for an installation."""
        data = await self._read_data()
        inst_id_str = str(installation_id)
        if inst_id_str in data:
            data[inst_id_str]['tier'] = tier
            await self._write_data(data)
