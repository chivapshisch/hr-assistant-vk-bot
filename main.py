import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
import uvicorn

from autorezacia.first_autorezacia import db_conn, init_hr_database
import config
import logirovanie
from routerswebhook import router as vk_router

logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_hr_database()
    logger.info("[БАЗА ДАННЫХ] Успешно подключена при старте сервера.")

    yield

    if db_conn:
        await db_conn.close()
        logger.info("[БАЗА ДАННЫХ] Соединение безопасно закрыто.")


app = FastAPI(title="hr bot", lifespan=lifespan)
app.include_router(vk_router)


@app.get("/health")
async def health():
    return {"status": "successful"}


if __name__ == "__main__":
    asyncio.get_event_loop().set_debug(True)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
