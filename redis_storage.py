import json

import redis.asyncio as redis

from config import REDIS_STORAGE_URL

STATE_TTL = 86400

redis_client = redis.from_url(
    REDIS_STORAGE_URL,
    decode_responses=True,
    max_connections=20,
)


async def get_user_state(user_id: int) -> str | None:
    return await redis_client.hget(f"vk_bot:session:{user_id}", "state")


async def set_user_state(user_id: int, state: str):
    key = f"vk_bot:session:{user_id}"
    pipe = redis_client.pipeline()
    pipe.hset(key, "state", state)
    pipe.expire(key, STATE_TTL)
    await pipe.execute()


async def get_user_data(user_id: int) -> dict:
    raw_data = await redis_client.hget(f"vk_bot:session:{user_id}", "data")
    return json.loads(raw_data) if raw_data else {}


async def set_user_data(user_id: int, data: dict):
    key = f"vk_bot:session:{user_id}"
    pipe = redis_client.pipeline()
    pipe.hset(key, "data", json.dumps(data, ensure_ascii=False))
    pipe.expire(key, STATE_TTL)
    await pipe.execute()


async def is_hr_authorized(user_id: int) -> bool:
    return bool(await redis_client.sismember("vk_bot:authorized_hr", str(user_id)))


async def authorize_hr(user_id: int):
    await redis_client.sadd("vk_bot:authorized_hr", str(user_id))


async def logout_hr(user_id: int):
    pipe = redis_client.pipeline()
    pipe.srem("vk_bot:authorized_hr", str(user_id))
    pipe.delete(f"vk_bot:session:{user_id}")
    await pipe.execute()


async def is_event_processed(event_id: str) -> bool:
    if not event_id:
        return False

    is_new = await redis_client.set(f"vk_bot:event:{event_id}", "1", ex=600, nx=True)
    return is_new is None
