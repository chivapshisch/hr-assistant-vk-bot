import logging
import random

import httpx

from config import VK_TOKEN

logger = logging.getLogger(__name__)


async def send_vk_message(user_id: int, text: str, keyboard: str = None):
    url = "https://api.vk.com/method/messages.send"

    payload = {
        "user_id": str(user_id),
        "message": text,
        "random_id": str(random.randint(1, 1000000)),
        "access_token": VK_TOKEN,
        "v": "5.199",
    }

    if keyboard:
        payload["keyboard"] = keyboard

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, data=payload)
            return response.json()
    except httpx.HTTPError as http_error:
        logger.error(f"Сетевая ошибка VK API: {http_error}")
        return {"error": "Ошибка сети при запросе к ВК"}
    except Exception as error:
        logger.exception(f"Неизвестная ошибка в send_vk_message: {error}")
        return {"error": str(error)}