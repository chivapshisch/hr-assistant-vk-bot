import logging
from typing import Optional

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)

db_conn: Optional[aiosqlite.Connection] = None


async def init_hr_database() -> Optional[str]:
    global db_conn

    db_conn = await aiosqlite.connect(DB_PATH, timeout=30.0)
    await db_conn.execute("PRAGMA journal_mode=WAL;")
    await db_conn.execute("PRAGMA synchronous=NORMAL;")
    await db_conn.execute("PRAGMA busy_timeout=30000;")

    async with db_conn.cursor() as cursor:
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS hr_managers (
                hr_id TEXT PRIMARY KEY,
                secret_key TEXT UNIQUE,
                name TEXT,
                organization TEXT
            )
            """
        )

        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS works (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hr_id TEXT,
                key_of_work TEXT UNIQUE,
                name_of_work TEXT,
                grafik TEXT,
                zarplata_min INTEGER,
                zarplata_max INTEGER,
                test TEXT
            )
            """
        )

        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS zaivki (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hr_id TEXT,
                key_of_work TEXT,
                name_of_work TEXT,
                opisanie TEXT,
                name TEXT,
                familia TEXT,
                otchestvo TEXT,
                city TEXT,
                number TEXT,
                ocenka TEXT
            )
            """
        )

        await cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_hr_auth
            ON hr_managers (secret_key, hr_id)
            """
        )

        await cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_works_key
            ON works (key_of_work)
            """
        )

        await cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_works_hr
            ON works (hr_id)
            """
        )

        await cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_zaivki_hr
            ON zaivki (hr_id)
            """
        )

        await db_conn.commit()

    return None


async def vhod_hr(user_id_hr: int, secret_key_hr: str) -> str:
    global db_conn

    if db_conn is None:
        logger.error("[База Данных] Соединение с БД не установлено!")
        return "error_db"

    clean_secret_key = str(secret_key_hr).strip()

    try:
        async with db_conn.cursor() as cursor:
            await cursor.execute(
                "SELECT hr_id FROM hr_managers WHERE secret_key = ?",
                (clean_secret_key,),
            )
            row = await cursor.fetchone()

            if row is None:
                return "not_found"

            current_db_hr_id = row[0]

            if current_db_hr_id is not None and current_db_hr_id != "":
                if current_db_hr_id == str(user_id_hr):
                    return "ok"
                return "already_used"

            await cursor.execute(
                "UPDATE hr_managers SET hr_id = ? WHERE secret_key = ?",
                (str(user_id_hr), clean_secret_key),
            )
            await db_conn.commit()
            logger.info(f"[База Данных] Ключ успешно активирован. HR {user_id_hr} привязан.")
            return "ok"

    except Exception as error:
        logger.exception(f"Ошибка в vhod_hr: {error}")
        return "error"


async def vhod_user(user_id: int, key_user: str):
    global db_conn

    if db_conn is None:
        logger.error("[База Данных] Соединение с БД не установлено!")
        return "error_db", None

    try:
        async with db_conn.cursor() as cursor:
            await cursor.execute(
                "SELECT id, name_of_work FROM works WHERE key_of_work = ?",
                (str(key_user).strip(),),
            )
            row = await cursor.fetchone()

            if row is None:
                return "not_found", None

            vacancy_id, vacancy_name = row

            logger.info(
                f"[База Данных] Пользователь {user_id} успешно ввел ключ от вакансии: {vacancy_name} (ID: {vacancy_id})"
            )
            return "ok", vacancy_id

    except Exception as error:
        logger.exception(f"Ошибка в vhod_user: {error}")
        return "error", None


async def get_analitika(user_id: int):
    global db_conn

    if db_conn is None:
        logger.error("[База Данных] Соединение с базой данных не установлено")
        return []

    try:
        async with db_conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT name_of_work, zarplata_min, zarplata_max
                FROM works
                WHERE hr_id = ?
                ORDER BY id
                """,
                (str(user_id),),
            )
            rows = await cursor.fetchall()

            analytics_list = []
            for name_of_work, salary_min, salary_max in rows:
                analytics_list.append(
                    {
                        "vakansia": name_of_work,
                        "min_zp": salary_min,
                        "max_zp": salary_max,
                    }
                )

            return analytics_list

    except Exception as error:
        logger.exception(f"[База Данных] Ошибка при получении аналитики: {error}")
        return []


async def delete_vakansia(user_id, number_udalenia_vakansia):
    global db_conn

    try:
        display_number = int(number_udalenia_vakansia)
    except (ValueError, TypeError):
        logger.warning(f"[База Данных] Передан некорректный номер вакансии: {number_udalenia_vakansia}")
        return "invalid_number"

    target_index = display_number - 1

    if db_conn is None:
        logger.error("[База Данных] Соединение с БД не установлено")
        return "error_connection"

    try:
        async with db_conn.cursor() as cursor:
            await cursor.execute(
                "SELECT id, name_of_work FROM works WHERE hr_id = ? ORDER BY id",
                (str(user_id),),
            )
            rows = await cursor.fetchall()

            if target_index < 0 or target_index >= len(rows):
                logger.warning(
                    f"[База Данных] Вакансия под номером {display_number} не найдена в базе (всего записей: {len(rows)})"
                )
                return "invalid_number"

            real_db_id, vacancy_name = rows[target_index]

            await cursor.execute(
                "DELETE FROM works WHERE id = ? AND hr_id = ?",
                (real_db_id, str(user_id)),
            )
            await db_conn.commit()

            logger.info(
                f"[База Данных] Запись успешно удалена: вакансия '{vacancy_name}' (ID в базе: {real_db_id})"
            )
            return "ok"

    except Exception as error:
        logger.exception(f"[База Данных] Критическая ошибка при удалении вакансии: {error}")
        try:
            await db_conn.rollback()
        except Exception:
            pass
        return "error"


async def get_a_key(user_id, number_vakansia_which_get_a_key):
    global db_conn

    try:
        display_number = int(number_vakansia_which_get_a_key)
    except (ValueError, TypeError):
        logger.warning(f"[База Данных] Передан некорректный номер вакансии: {number_vakansia_which_get_a_key}")
        return "invalid_number"

    target_index = display_number - 1

    if db_conn is None:
        logger.error("[База Данных] Соединение с БД не установлено")
        return "error_connection"

    try:
        async with db_conn.cursor() as cursor:
            await cursor.execute(
                "SELECT key_of_work FROM works WHERE hr_id = ? ORDER BY id",
                (str(user_id),),
            )
            rows = await cursor.fetchall()

            if target_index < 0 or target_index >= len(rows):
                logger.warning(
                    f"[База Данных] Вакансия под номером {display_number} не найдена в базе (всего записей: {len(rows)})"
                )
                return "invalid_number"

            return rows[target_index][0]

    except Exception as error:
        logger.exception(f"[База Данных] Критическая ошибка при получении ключа вакансии: {error}")
        return "error"


async def get_main_about_vakansia(vacancy_id: int) -> str:
    global db_conn

    if db_conn is None:
        logger.error("[База Данных] Соединение с БД не установлено")
        return ""

    try:
        async with db_conn.cursor() as cursor:
            await cursor.execute(
                "SELECT test FROM works WHERE id = ?",
                (int(vacancy_id),),
            )
            row = await cursor.fetchone()
            return row[0] if row and row[0] else ""

    except Exception as error:
        logger.exception(f"[База Данных] Критическая ошибка при получении критериев вакансии: {error}")
        return ""


async def get_otkliki(hr_id):
    global db_conn

    if db_conn is None:
        logger.error("[База Данных] Соединение с БД не установлено")
        return []

    try:
        async with db_conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT name_of_work, familia, name, otchestvo, city, number, ocenka, opisanie
                FROM zaivki
                WHERE hr_id = ?
                ORDER BY CAST(ocenka AS INTEGER) DESC
                """,
                (str(hr_id),),
            )
            rows = await cursor.fetchall()

            responses_list = []
            for (
                name_of_work,
                familia,
                name,
                otchestvo,
                city,
                number,
                ocenka,
                opisanie,
            ) in rows:
                responses_list.append(
                    {
                        "vakansia": name_of_work,
                        "fio": f"{familia} {name} {otchestvo}".strip(),
                        "city": city,
                        "number": number,
                        "ocenka": ocenka,
                        "opisanie": opisanie,
                    }
                )
            return responses_list

    except Exception as error:
        logger.exception(f"[База Данных] Ошибка при получении откликов: {error}")
        return []
