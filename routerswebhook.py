import json
import logging

from celery import chain
from fastapi import APIRouter, Request, Response

from autorezacia.first_autorezacia import (
    delete_vakansia,
    get_a_key,
    get_analitika,
    get_main_about_vakansia,
    get_otkliki,
    vhod_hr,
    vhod_user,
)
from config import VK_CONFIRMATION_STRING
from keyboard import analit, keyboard_hr, keyboard_main, yes_or_no
from parser_pdf import (
    ask_yandex_bg,
    download_vk_pdf,
    process_pdf_to_json,
    save_to_db,
    save_to_db_zaivku,
)
from promts import PROMT_NEW_VAKANSIA, PROMT_OCENKI_USERA
from redis_storage import (
    authorize_hr,
    get_user_data,
    get_user_state,
    is_event_processed,
    is_hr_authorized,
    logout_hr,
    set_user_data,
    set_user_state,
)
from vk_service import send_vk_message

logger = logging.getLogger(__name__)
router = APIRouter()




@router.post("/vk-webhook")
async def vk_callback(request: Request):
    data = await request.json()

    if data.get("type") == "confirmation":
        return Response(content=VK_CONFIRMATION_STRING)

    if data.get("type") == "message_new":
        event_id = data.get("event_id")
        if await is_event_processed(event_id):
            return Response(content="ok")

        message_object = data["object"]["message"]
        user_id = message_object["from_id"]
        user_text = message_object["text"]
        payload_raw = message_object.get("payload")

        current_state = await get_user_state(user_id)

        if payload_raw:
            payload = json.loads(payload_raw)
            command = payload.get("command")

            if command == "start":
                await set_user_state(user_id, "MAIN_MENU")
                welcome_text = (
                    "Привет! Начнем работу. Сначала авторизуемся.\n\n"
                    "А вот тестовый ключ для пользователя: key_1794897643_392\n\n"

                )
                await send_vk_message(user_id, welcome_text, keyboard_main)
                return Response(content="ok")

            if command == "vhod_hr":
                await set_user_state(user_id, "HR_VVOD_KLUCHA")
                await send_vk_message(user_id, "Введите ваш ключ")
                return Response(content="ok")

            if command == "new_vakansia":
                await set_user_data(user_id, {})
                await set_user_state(user_id, "HR_NEW_VAKANSIA_PDF")
                await send_vk_message(
                    user_id,
                    "Скиньте файл в формате PDF, в котором будут отражены основные требования и описание вакансии, чтобы наш ИИ-агент мог оценивать кандидатов.",
                )
                return Response(content="ok")

            if command == "see_otkliki":
                await set_user_state(user_id, "HR_AUTORIZOVAN")
                otkliki = await get_otkliki(user_id)

                if not otkliki:
                    await send_vk_message(user_id, "📭 Пока нет ни одного отклика от кандидатов.", keyboard_hr)
                    return Response(content="ok")

                responses_text = "📊 Отклики кандидатов (по убыванию оценки):\n\n"
                for index, item in enumerate(otkliki, start=1):
                    responses_text += (
                        f"{index}. Вакансия: {item['vakansia']}\n"
                        f"👤 {item['fio']} ({item['city']})\n"
                        f"📞 {item['number']}\n"
                        f"⭐ Оценка ИИ: {item['ocenka']}/5\n"
                        f"📝 Резюме ИИ: {item['opisanie']}\n"
                        f"-------------------------------------------\n\n"
                    )

                await send_vk_message(user_id, responses_text[:4000], keyboard_hr)
                return Response(content="ok")




            

            if command == "poluchit_analitiku":
                await set_user_state(user_id, "HR_AUTORIZOVAN")
                await send_vk_message(user_id, "⏳ Начинаем собирать аналитику...")
                try:
                    analytics_items = await get_analitika(user_id)
                    if not analytics_items:
                        await send_vk_message(user_id, "У вас пока нет активных вакансий.", analit)
                        return Response(content="ok")

                    analytics_text = "📊 Ваша аналитика:\n\n"
                    for index, work in enumerate(analytics_items, start=1):
                        analytics_text += (
                            f"{index}. {work['vakansia']}\n"
                            f"💰 Зарплата: {work['min_zp']} – {work['max_zp']}\n"
                            f"-------------------------------------------\n\n"
                        )
                    await send_vk_message(user_id, analytics_text[:4000], analit)
                except Exception as error:
                    logger.exception(f"Ошибка при получении аналитики для HR {user_id}: {error}")
                    await send_vk_message(user_id, "❌ Не удалось собрать аналитику. Попробуйте позже.", keyboard_hr)
                return Response(content="ok")




            if command == "delet_vakansia":
                await set_user_state(user_id, "UDALENIE")
                await send_vk_message(user_id, "Укажите номер вакансии, которую хотите удалить:")
                return Response(content="ok")

            if command == "del_vakansia":
                if current_state != "UDALENIE_OZHIDANIE":
                    await send_vk_message(user_id, "⚠️ Действие устарело. Выберите удаление заново.", keyboard_hr)
                    return Response(content="ok")

                user_data = await get_user_data(user_id)
                saved_number = user_data.get("delete_num")
                await set_user_state(user_id, "HR_AUTORIZOVAN")

                try:
                    vacancy_number = int(saved_number)
                    delete_status = await delete_vakansia(user_id, vacancy_number)
                    if delete_status == "ok":
                        await send_vk_message(user_id, f"✅ Вакансия №{vacancy_number} успешно удалена.", keyboard_hr)
                    elif delete_status == "invalid_number":
                        await send_vk_message(
                            user_id,
                            f"⚠️ Номер №{vacancy_number} не найден в вашем списке вакансий.",
                            keyboard_hr,
                        )
                    else:
                        await send_vk_message(user_id, "❌ Не удалось удалить вакансию из-за ошибки БД.", keyboard_hr)
                except Exception as error:
                    logger.exception(f"Ошибка при удалении вакансии: {error}")
                    await send_vk_message(user_id, "❌ Произошла ошибка при удалении.", keyboard_hr)
                return Response(content="ok")

            if command == "otmena_delet_vakansia":
                await set_user_state(user_id, "HR_AUTORIZOVAN")
                await send_vk_message(user_id, "❌ Удаление отменено.", keyboard_hr)
                return Response(content="ok")

            if command == "poluchit_kluch":
                await set_user_state(user_id, "GET_KEY")
                await send_vk_message(user_id, "Укажите номер вакансии, ключ которой Вы хотите получить")
                return Response(content="ok")


            if command == "change_vakansia":
                await send_vk_message(user_id, "🚧 Этот раздел пока в разработке.", keyboard_hr)
                return Response(content="ok")




            if command == "vhod_user":
                await set_user_state(user_id, "USER_VVOD_KLUCHA")
                await send_vk_message(user_id, "Введите ключ, переданный Вам работодателем")
                return Response(content="ok")



        if current_state == "HR_VVOD_KLUCHA":
            auth_status = await vhod_hr(user_id, user_text)

            if auth_status == "ok":
                await authorize_hr(user_id)
                await set_user_state(user_id, "HR_AUTORIZOVAN")
                await send_vk_message(user_id, "✅ Авторизация успешна! Добро пожаловать.", keyboard_hr)
                return Response(content="ok")
            if auth_status == "already_used":
                await set_user_state(user_id, "MAIN_MENU")
                await send_vk_message(user_id, "⚠️ Этот ключ уже активирован другим аккаунтом.", keyboard_main)
                return Response(content="ok")

            await send_vk_message(user_id, "❌ Неверный ключ. Попробуйте еще раз или напишите 'привет' для отмены.")
            return Response(content="ok")


        if current_state == "USER_VVOD_KLUCHA":
            status, vacancy_id = await vhod_user(user_id, user_text)

            if status == "ok":
                await set_user_data(user_id, {"vacancy_id": vacancy_id})
                await set_user_state(user_id, "USER_WAITING_FOR_PDF")
                await send_vk_message(user_id, "✅ Ключ принят! Пожалуйста, отправьте ваше резюме в формате PDF.")
                return Response(content="ok")
            if status == "not_found":
                await send_vk_message(user_id, "❌ Вакансия с таким ключом не найдена. Проверьте правильность ввода.")
                return Response(content="ok")

            await send_vk_message(user_id, "🔥 Произошла ошибка базы данных. Попробуйте позже.")
            return Response(content="ok")

        if current_state == "USER_WAITING_FOR_PDF":
            try:
                temp_file_path = await download_vk_pdf(user_id, message_object)
                if not temp_file_path:
                    return Response(content="ok")

                user_data = await get_user_data(user_id)
                vacancy_id = user_data.get("vacancy_id", "")
                vacancy_criteria = await get_main_about_vakansia(vacancy_id)
                evaluation_prompt = f"{PROMT_OCENKI_USERA}\n\nНа что обратить внимание:\n{vacancy_criteria}"

                pipeline = chain(
                    process_pdf_to_json.s(temp_file_path)
                    | ask_yandex_bg.s(promt=evaluation_prompt)
                    | save_to_db_zaivku.s(user_id=user_id, key_of_work=vacancy_id)
                )
                pipeline.delay()

                await set_user_state(user_id, "MAIN_MENU")
                await send_vk_message(user_id, "✅ Ваше резюме принято в обработку!", keyboard_main)

            except Exception as error:
                logger.exception(f"Не удалось обработать PDF резюме для user_id={user_id}: {error}")
                await send_vk_message(
                    user_id,
                    "🔥 Произошла внутренняя ошибка при скачивании файла. Попробуйте загрузить еще раз.",
                )

            return Response(content="ok")

 
        if current_state == "HR_NEW_VAKANSIA_PDF":
            try:
                temp_file_path = await download_vk_pdf(user_id, message_object)
                if not temp_file_path:
                    return Response(content="ok")

                pipeline = chain(
                    process_pdf_to_json.s(temp_file_path)
                    | ask_yandex_bg.s(promt=PROMT_NEW_VAKANSIA)
                    | save_to_db.s(user_id)
                )
                pipeline.delay()

                await set_user_state(user_id, "HR_AUTORIZOVAN")
                await send_vk_message(
                    user_id,
                    "⚙️ Вакансия отправлена на анализ ИИ! Вы можете продолжать работу с меню.",
                    keyboard_hr,
                )

            except Exception as error:
                logger.exception(f"Не удалось обработать PDF вакансии для HR {user_id}: {error}")
                await send_vk_message(
                    user_id,
                    "🔥 Произошла внутренняя ошибка при скачивании файла. Попробуйте загрузить еще раз.",
                    keyboard_hr,
                )

            return Response(content="ok")

        if current_state == "UDALENIE":
            clean_number = user_text.strip()
            if not clean_number.isdigit():
                await send_vk_message(user_id, "⚠️ Пожалуйста, введите корректный числовой номер вакансии (например: 1).")
                return Response(content="ok")

            await set_user_data(user_id, {"delete_num": int(clean_number)})
            await set_user_state(user_id, "UDALENIE_OZHIDANIE")
            await send_vk_message(user_id, f"Подтвердите удаление вакансии номер {clean_number}:", yes_or_no)
            return Response(content="ok")

        if current_state == "UDALENIE_OZHIDANIE":
            await send_vk_message(
                user_id,
                "⚠️ Пожалуйста, нажмите кнопку «Удалить» или «Отмена» на клавиатуре.",
                yes_or_no,
            )
            return Response(content="ok")

        if current_state == "GET_KEY":
            await set_user_state(user_id, "HR_AUTORIZOVAN")
            vacancy_key = await get_a_key(user_id, user_text)

            if vacancy_key == "invalid_number":
                await send_vk_message(user_id, "⚠️ Вакансия с таким номером не найдена.", keyboard_hr)
                return Response(content="ok")
            if vacancy_key in ("error_connection", "error"):
                await send_vk_message(user_id, "❌ Не удалось получить ключ из-за ошибки БД.", keyboard_hr)
                return Response(content="ok")

            await send_vk_message(user_id, vacancy_key)
            await send_vk_message(user_id, "Ловите ключ, отправляйте претенденту на вакансию", keyboard_hr)
            return Response(content="ok")



            
        if user_text.lower() in ("выйти", "выход", "/logout"):
            await logout_hr(user_id)
            await set_user_state(user_id, "MAIN_MENU")
            await send_vk_message(user_id, "🚪 Вы вышли из аккаунта HR. Выберите роль:", keyboard_main)
            return Response(content="ok")

        hr_authorized = await is_hr_authorized(user_id)

        if user_text.lower() == "привет":
            if hr_authorized or current_state == "HR_AUTORIZOVAN":
                await send_vk_message(
                    user_id,
                    "Вы уже авторизованы в системе! Выберите одно из предложенных действий",
                    keyboard_hr,
                )
            else:
                await set_user_state(user_id, "MAIN_MENU")
                welcome_text = (
                    "Привет! Начнем работу. Сначала авторизуемся.\n\n"
                    "Лови тестовый ключ hr: 3424184\n\n"
                    "А вот тестовый ключ для пользователя: key_1794897643_392\n\n"
                    "Выберите вашу роль на клавиатуре ниже:"
                )
                await send_vk_message(user_id, welcome_text, keyboard_main)
            return Response(content="ok")

        if hr_authorized or current_state == "HR_AUTORIZOVAN":
            await send_vk_message(user_id, "⚠️ Я вас не понял. Пожалуйста, пользуйтесь кнопками меню.", keyboard_hr)
        else:
            await send_vk_message(
                user_id,
                "🤔 Неизвестная команда. Пожалуйста, выберите действие на клавиатуре ниже:",
                keyboard_main,
            )

        return Response(content="ok")

    return Response(content="ok")


