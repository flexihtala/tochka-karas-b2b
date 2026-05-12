import httpx

from apps.skus.schemas.moderation import ProductModerationEventSchema
from settings import Settings


class ModerationRepository:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def send_product_event(self, event: ProductModerationEventSchema) -> None:
        url = f'{self.settings.moderation_url.rstrip("/")}/api/v1/events/product'
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                url,
                headers={'X-Service-Key': self.settings.b2b_to_mod_key},
                json=event.model_dump(mode='json'),
            )
            response.raise_for_status()
