import asyncio

import httpx
from sqlalchemy import select

from ..database import SessionLocal
from ..models import Webhook
import hmac
import hashlib
import json

def create_signature(
    payload: dict,
    secret: str,
) -> str:

    body = json.dumps(
        payload,
        sort_keys=True
    )

    return hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()

async def send_webhook(
    url: str,
    payload: dict,
    secret: str,
) -> bool:
    """
    Send a webhook with retry logic.
    """
    signature = create_signature(payload, secret,)
    headers = {
        "X-Signature": signature,
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=10,
                )

                response.raise_for_status()

            return True

        except Exception as exc:
            print(
                f"Webhook delivery failed "
                f"(attempt {attempt + 1}/3): {exc}"
            )

            if attempt < 2:
                await asyncio.sleep(2)

    return False


async def notify_webhooks(
    payload: dict,
) -> None:
    """
    Send payload to all enabled webhooks.
    """

    db = SessionLocal()

    try:
        webhooks = db.execute(
            select(Webhook).where(
                Webhook.enabled.is_(True)
            )
        ).scalars().all()

        if not webhooks:
            return

        tasks = [
            send_webhook(
                webhook.url,
                payload,
                webhook.secret,
            )
            for webhook in webhooks
        ]

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

    finally:
        db.close()


async def test_webhook(
    url: str,
) -> bool:
    """
    Send a test event.
    """

    return await send_webhook(
        url,
        {
            "event": "test",
            "message": "Webhook test successful",
        },
        secret,
    )