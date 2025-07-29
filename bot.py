import os
import json
from oauth2client.service_account import ServiceAccountCredentials

# Считываем JSON из переменной окружения
creds_json = os.getenv("GOOGLE_CREDS_JSON")

if not creds_json:
    raise ValueError("Переменная окружения GOOGLE_CREDS_JSON не установлена")

# Преобразуем строку обратно в словарь
creds_dict = json.loads(creds_json)

# Настройка доступа к Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# Используем from_json_keyfile_dict вместо from_json_keyfile_name
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
import logging
import re
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.types import KeyboardButton as AiogramKeyboardButton
from dotenv import load_dotenv
import asyncio
from datetime import datetime

# Логирование
logging.basicConfig(level=logging.INFO)

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME')

# Авторизация Google Sheets
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

# Память для хранения данных
user_data = {}

# Клавиатуры
start_kb = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[[AiogramKeyboardButton(text="Оставить заявку")]]
)

region_kb = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,
    keyboard=[
        [AiogramKeyboardButton(text="Южнее"), AiogramKeyboardButton(text="Севернее")],
        [AiogramKeyboardButton(text="Центр")]
    ]
)

period_kb = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,
    keyboard=[
        [AiogramKeyboardButton(text="Семестр"), AiogramKeyboardButton(text="2 недели")],
        [AiogramKeyboardButton(text="Месяц"), AiogramKeyboardButton(text="Год")]
    ]
)

level_kb = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,
    keyboard=[
        [AiogramKeyboardButton(text="Начальный"), AiogramKeyboardButton(text="Средний")],
        [AiogramKeyboardButton(text="Продвинутый"), AiogramKeyboardButton(text="Свободно")]
    ]
)

visa_kb = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,
    keyboard=[[AiogramKeyboardButton(text="Да"), AiogramKeyboardButton(text="Нет")]]
)

# Валидация телефона
def validate_phone(phone):
    pattern = re.compile(r"^\+?\d{10,15}$")
    return bool(pattern.match(phone))

# Инициализация бота и диспетчера — вынесена из main()
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Здравствуйте! Нажмите кнопку «Оставить заявку», чтобы начать заполнение формы.",
        reply_markup=start_kb
    )

@dp.message(lambda message: message.text == "Оставить заявку")
async def ask_name(message: types.Message):
    await message.answer("Пожалуйста, введите ваше имя:")
    user_data[message.from_user.id] = {"step": "waiting_for_name"}

@dp.message()
async def handle_data(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        await message.answer("Пожалуйста, нажмите 'Оставить заявку' для начала.", reply_markup=start_kb)
        return

    step = user_data[user_id].get("step")
    text = message.text.strip()

    if step == "waiting_for_name":
        user_data[user_id]["name"] = text
        user_data[user_id]["step"] = "waiting_for_phone"
        await message.answer("Введите ваш телефон (только цифры, можно с плюсом):")

    elif step == "waiting_for_phone":
        if not validate_phone(text):
            await message.answer("Пожалуйста, введите корректный номер телефона (от 10 до 15 цифр).")
            return
        user_data[user_id]["phone"] = text
        user_data[user_id]["telegram"] = f"@{message.from_user.username}" if message.from_user.username else "Не указан"
        user_data[user_id]["step"] = "waiting_for_region"
        await message.answer("Какой регион вас интересует?", reply_markup=region_kb)

    elif step == "waiting_for_region":
        if text not in ["Южнее", "Севернее", "Центр"]:
            await message.answer("Пожалуйста, выберите вариант кнопками.")
            return
        user_data[user_id]["region"] = text
        user_data[user_id]["step"] = "waiting_for_period"
        await message.answer("На какой промежуток времени обучения вы нацелены?", reply_markup=period_kb)

    elif step == "waiting_for_period":
        valid_periods = ["Семестр", "2 недели", "Месяц", "Год"]
        if text not in valid_periods:
            await message.answer("Пожалуйста, выберите один из вариантов кнопками.")
            return
        user_data[user_id]["period"] = text
        user_data[user_id]["step"] = "waiting_for_level"
        await message.answer("Выберите ваш уровень владения языком:", reply_markup=level_kb)

    elif step == "waiting_for_level":
        valid_levels = ["Начальный", "Средний", "Продвинутый", "Свободно"]
        if text not in valid_levels:
            await message.answer("Пожалуйста, выберите уровень кнопками.")
            return
        user_data[user_id]["level"] = text
        user_data[user_id]["step"] = "waiting_for_start_dates"
        await message.answer(
            "В какие даты планируете приступить к обучению? \n(Например: через 1 неделю, через 2 недели и т.д.)",
            reply_markup=ReplyKeyboardRemove()
        )

    elif step == "waiting_for_start_dates":
        user_data[user_id]["start_dates"] = text
        user_data[user_id]["step"] = "waiting_for_visa"
        await message.answer("Нужна ли вам виза?", reply_markup=visa_kb)

    elif step == "waiting_for_visa":
        if text not in ["Да", "Нет"]:
            await message.answer("Пожалуйста, выберите 'Да' или 'Нет' кнопками.")
            return
        user_data[user_id]["visa"] = text
        user_data[user_id]["step"] = "waiting_for_budget"
        await message.answer(
            "Укажите ваш бюджет. \n(Учтите еду, проживание, билеты и обучение.)",
            reply_markup=ReplyKeyboardRemove()
        )

    elif step == "waiting_for_budget":
        user_data[user_id]["budget"] = text
        user_data[user_id]["step"] = "waiting_for_message"
        await message.answer("Если хотите, оставьте дополнительное сообщение (если нет — просто напишите 'Нет'):")

    elif step == "waiting_for_message":
        user_data[user_id]["message"] = text if text.lower() != "нет" else ""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Запись в таблицу в правильном порядке
        row = [
            user_data[user_id].get("name", ""),
            user_data[user_id].get("phone", ""),
            user_data[user_id].get("telegram", ""),
            user_data[user_id].get("region", ""),
            user_data[user_id].get("period", ""),
            user_data[user_id].get("level", ""),
            user_data[user_id].get("start_dates", ""),
            user_data[user_id].get("visa", ""),
            user_data[user_id].get("budget", ""),
            user_data[user_id].get("message", ""),
            now
        ]

        sheet.append_row(row)

        await message.answer(
            "Спасибо за вашу заявку! С вами свяжется менеджер, как только будет свободен.",
            reply_markup=start_kb
        )
        user_data.pop(user_id, None)

    else:
        await message.answer("Пожалуйста, начните заново с команды /start.", reply_markup=start_kb)


async def main():
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
