import json
import logging
import os
import random
import sqlite3
import time

import httpx
import pymupdf as fitz
from celery import Celery
from langchain_community.llms import YandexGPT
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from config import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    DB_PATH,
    YANDEX_API_KEY,
    YANDEX_FOLDER_ID,
)
import logirovanie
from vk_service import send_vk_message

logger = logging.getLogger(__name__)

app = Celery(
    "parser_pdf",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn



@app.task
def process_pdf_to_json(file_path: str) -> str:
    logger.info(f"[Воркер] Начало извлечения текста из PDF: {file_path}...")
    try:
        doc = fitz.open(file_path)
        text_blocks = []
        for page in doc:
            page_text = page.get_text("text", sort=True)
            cleaned_text = page_text.strip()
            if cleaned_text:
                text_blocks.append(cleaned_text)
        doc.close()

        if os.path.exists(file_path):
            os.remove(file_path)

        full_text = "\n--- СТРАНИЦА ---\n".join(text_blocks)
        json_payload = {"document_text": full_text.strip()}
        return json.dumps(json_payload, ensure_ascii=False, indent=4)

    except Exception as error:
        logger.exception(f"[Воркер] Ошибка при парсинге PDF {file_path}: {error}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        return json.dumps({"error": f"Не удалось распарсить: {str(error)}"}, ensure_ascii=False)


@app.task
def ask_yandex_bg(json_data: str, promt: str):
    logger.info("[Воркер] Шаг 2: Вход в задачу ask_yandex_bg...")

    if not YANDEX_FOLDER_ID or not YANDEX_API_KEY:
        error_msg = "[Воркер] ❌ Ошибка: Не удалось прочитать YANDEX_FOLDER_ID или YANDEX_API_KEY из config.py!"
        logger.error(error_msg)
        return {"error": error_msg, "vacancy_name": "Ошибка конфигурации ИИ"}

    try:
        model = YandexGPT(
            folder_id=YANDEX_FOLDER_ID,
            api_key=YANDEX_API_KEY,
            model_name="yandexgpt-lite",
            temperature=0.7,
        )
    except Exception as error:
        logger.exception(f"[Воркер] ❌ Ошибка создания модели YandexGPT: {error}")
        return {"error": str(error), "vacancy_name": "Ошибка инициализации ИИ"}

    prompt = PromptTemplate.from_template(promt)
    output_parser = StrOutputParser()
    chain_llm = prompt | model | output_parser

    logger.info("[Воркер] Отправляю запрос в YandexGPT...")
    start_time = time.time()

    try:
        response = chain_llm.invoke({"vacancy_data": json_data})
        execution_time = time.time() - start_time
        logger.info(f"[Воркер] Ответ от ИИ успешно получен за {execution_time:.2f} сек.")

        clean_response = response.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(clean_response)
    except Exception as error:
        logger.exception(f"[Воркер] ❌ Ошибка выполнения/парсинга цепочки ЛЛМ: {error}")
        return {"status": "error", "error": str(error)}


@app.task
def save_to_db(ai_data, hr_id: int):
    logger.info(f"[База Данных] Начинаю обработку данных для HR ID: {hr_id}...")

    if isinstance(ai_data, str):
        try:
            data = json.loads(ai_data)
        except Exception as error:
            logger.exception(f"[База Данных] Ошибка: не удалось распарсить строку в JSON: {error}")
            return "Error"
    else:
        data = ai_data

    if not isinstance(data, dict):
        logger.error("[База Данных] Ошибка: данные пришли в неверном формате")
        return "Error"

    try:
        title = data.get("vacancy_name", "Не указано")
        schedule = data.get("schedule", "Не указано")

        try:
            salary_min = int(data.get("salary_min", 0))
        except (ValueError, TypeError):
            salary_min = 0

        try:
            salary_max = int(data.get("salary_max", 0))
        except (ValueError, TypeError):
            salary_max = 0

        criteria_list = data.get("criteria", [])
        criteria_text = (
            ", ".join(str(criterion) for criterion in criteria_list)
            if isinstance(criteria_list, list)
            else str(criteria_list)
        )

        generated_key = f"key_{int(time.time())}_{random.randint(100, 999)}"

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO works (hr_id, key_of_work, name_of_work, grafik, zarplata_min, zarplata_max, test)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(hr_id),
                    str(generated_key),
                    str(title),
                    str(schedule),
                    salary_min,
                    salary_max,
                    str(criteria_text),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info(f"[База Данных] Успешно сохранена вакансия: '{title}' для HR-менеджера {hr_id}")
        return "Saved"

    except Exception as error:
        logger.exception(f"[База Данных] Ошибка при сохранении в SQLite: {error}")
        return "Error"



@app.task
def save_to_db_zaivku(ai_data, user_id: int, key_of_work: str):
    logger.info(f"[База Данных] Начинаю обработку данных для пользователя ID: {user_id}...")

    if isinstance(ai_data, str):
        try:
            data = json.loads(ai_data)
        except Exception as error:
            logger.exception(f"[База Данных] Ошибка: не удалось распарсить строку в JSON: {error}")
            return "Error"
    else:
        data = ai_data

    if not isinstance(data, dict):
        logger.error("[База Данных] Ошибка: данные пришли в неверном формате")
        return "Error"

    try:
        opisanie = data.get("opisanie", "Не указано")
        name = data.get("name", "Не указано")
        familia = data.get("familia", "Не указано")
        otchestvo = data.get("otchestvo", "Не указано")
        city = data.get("city", "Не указано")
        number = data.get("number", "Не указано")
        ocenka = data.get("ocenka", 0)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT hr_id, name_of_work, key_of_work FROM works WHERE id = ?",
                (int(key_of_work),),
            )
            work_row = cursor.fetchone()

            if not work_row:
                logger.error(f"[База Данных] Ошибка: вакансия с ID '{key_of_work}' не найдена в таблице works!")
                return "Error"

            hr_id, name_of_work, real_key_of_work = work_row

            cursor.execute(
                """
                INSERT INTO zaivki (
                    hr_id, key_of_work, name_of_work, opisanie,
                    name, familia, otchestvo, city, number, ocenka
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(hr_id),
                    str(real_key_of_work),
                    str(name_of_work),
                    str(opisanie),
                    str(name),
                    str(familia),
                    str(otchestvo),
                    str(city),
                    str(number),
                    str(ocenka),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info(f"[База Данных] Успешно сохранена заявка на вакансию {real_key_of_work} для пользователя {user_id}")
        return "Saved"

    except Exception as error:
        logger.exception(f"[База Данных] Ошибка при сохранении в SQLite: {error}")
        return "Error"


async def download_vk_pdf(user_id: int, message_object: dict) -> str | None:
    attachments = message_object.get("attachments", [])
    if not attachments:
        await send_vk_message(user_id, "⚠️ Вы не прикрепили файл. Пожалуйста, отправьте именно PDF-документ.")
        return None

    pdf_attachment = next(
        (
            attachment["doc"]
            for attachment in attachments
            if attachment.get("type") == "doc" and attachment["doc"].get("ext") == "pdf"
        ),
        None,
    )
    if not pdf_attachment:
        await send_vk_message(user_id, "❌ Ошибка: Файл должен быть строго в формате PDF. Попробуйте еще раз.")
        return None

    download_url = pdf_attachment.get("url")
    if not download_url:
        logger.warning(f"ВК не предоставил прямую ссылку для скачивания PDF (user_id={user_id})")
        await send_vk_message(user_id, "❌ Не удалось получить ссылку на файл от ВК. Попробуйте загрузить его заново.")
        return None

    file_name = pdf_attachment.get("title", "document.pdf")
    await send_vk_message(user_id, f"📥 Файл '{file_name}' получен. Начинаем обработку...")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        response = await client.get(download_url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Не удалось скачать файл. Статус-код от VK: {response.status_code}")

    os.makedirs("temp_pdfs", exist_ok=True)
    temp_file_path = f"temp_pdfs/{user_id}_{int(time.time())}.pdf"
    with open(temp_file_path, "wb") as pdf_file:
        pdf_file.write(response.content)

    logger.info(f"Файл сохранен локально: {temp_file_path}")
    return temp_file_path


