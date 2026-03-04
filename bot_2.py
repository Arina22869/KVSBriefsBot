import logging
import sqlite3
import csv
import requests
from contextlib import contextmanager
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
import asyncio
from io import StringIO

# ============= НАСТРОЙКИ =============
TOKEN = "8797047074:AAEHlaYsh26Jf-GsA4G54C-46AcSHTP_uMw"
ADMIN_IDS = [1665864236]

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSb7eq1Jol47Xa4Bu714QMQl8RNIleLDQ2jhQecLIcrnWIpgLlCxoGQH3dw9EKZhQfMI-czGjnfuM_F/pub?output=csv"
# =====================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ============= БАЗА ДАННЫХ =============
@contextmanager
def get_db():
    conn = sqlite3.connect('briefs.db')
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS briefs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                status TEXT,
                deadline TEXT,
                contact TEXT,
                chat_id INTEGER
            )
        ''')
        conn.commit()

# ============= ПОЛУЧЕНИЕ ДАННЫХ ИЗ CSV =============
def fetch_csv_data():
    try:
        response = requests.get(CSV_URL)
        response.encoding = 'utf-8'
        csv_data = response.text
        reader = csv.reader(StringIO(csv_data))
        rows = list(reader)
        return rows if len(rows) >= 2 else []
    except Exception as e:
        logging.error(f"Ошибка загрузки CSV: {e}")
        return None

def get_user_briefs_from_csv(chat_id):
    rows = fetch_csv_data()
    if rows is None:
        return None
    if not rows:
        return []
    
    chat_id_str = str(chat_id)
    results = []
    
    for row in rows[1:]:
        if len(row) < 10:
            continue
        if row[0].strip() == chat_id_str:
            results.append({
                "zakazchik": row[1] if len(row) > 1 else "",
                "brief": row[2] if len(row) > 2 else "",
                "position": row[3] if len(row) > 3 else "",
                "status": row[4] if len(row) > 4 else "",
                "zapolneno": row[5].strip().upper() == "TRUE" if len(row) > 5 else False,
                "prozvon": row[6].strip().upper() == "TRUE" if len(row) > 6 else False,
                "propisano": row[7].strip().upper() == "TRUE" if len(row) > 7 else False,
                "soglasovano": row[8].strip().upper() == "TRUE" if len(row) > 8 else False,
                "zakryto": row[9].strip().upper() == "TRUE" if len(row) > 9 else False,
            })
    
    return results

# ============= КОМАНДЫ ДЛЯ ВСЕХ =============
@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        f"👋 Привет, {message.from_user.full_name}!\n\n"
        "🤖 Я бот для отслеживания статуса брифов.\n"
        "📌 Если ты заказчик — просто отправь /status\n"
        "🛠 Если ты активист — используй /menu"
    )
    await message.answer(text)

@dp.message(Command("status"))
async def cmd_status(message: Message):
    chat_id = message.from_user.id
    briefs = get_user_briefs_from_csv(chat_id)
    
    if briefs is None:
        await message.answer("❌ Ошибка загрузки данных. Попробуй позже.")
        return
    
    if not briefs:
        await message.answer("📭 У тебя пока нет активных брифов.")
        return
    
    grouped = {}
    for item in briefs:
        brief_name = item["brief"]
        if brief_name not in grouped:
            grouped[brief_name] = []
        grouped[brief_name].append(item)
    
    response = "📋 Твои брифы:\n\n"
    for brief_name, items in grouped.items():
        response += f"🎯 {brief_name}\n\n"
        for idx, item in enumerate(items, 1):
            response += f"{idx}. {item['position']}\n"
            response += f"   📊 Статус: {item['status']}\n"
            response += f"   ✅ Заполнено: {'✅' if item['zapolneno'] else '⬜'}\n"
            response += f"   📞 Прозвон: {'✅' if item['prozvon'] else '⬜'}\n"
            response += f"   📝 Прописано: {'✅' if item['propisano'] else '⬜'}\n"
            response += f"   🤝 Согласовано: {'✅' if item['soglasovano'] else '⬜'}\n"
            response += f"   🔒 Закрыто: {'✅' if item['zakryto'] else '⬜'}\n\n"
    
    await message.answer(response)

# ============= АДМИН-КОМАНДЫ =============
def is_admin(user_id):
    return user_id in ADMIN_IDS

@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для активистов.")
        return
    
    text = (
        "🛠 Меню активиста\n\n"
        "• /add — добавить запись в локальную БД\n"
        "• /list — список всех локальных записей\n"
        "• /set_status — изменить статус записи\n"
        "• /delete — удалить запись\n"
        "• /link — привязать заказчика к записи\n\n"
        "📎 Данные из Google Таблицы подтягиваются автоматически."
    )
    await message.answer(text)

@dp.message(Command("add"))
async def cmd_add(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=4)
    if len(args) < 5:
        await message.answer("📝 Формат: /add Компания Статус Дедлайн Контакт\nПример: /add ООО Пример В работе 25.04.2024 @ivanov")
        return
    
    company, status, deadline, contact = args[1], args[2], args[3], args[4]
    with get_db() as conn:
        conn.execute("INSERT INTO briefs (company, status, deadline, contact) VALUES (?, ?, ?, ?)",
                     (company, status, deadline, contact))
        conn.commit()
    await message.answer(f"✅ Запись для {company} добавлена в локальную БД!")

@dp.message(Command("list"))
async def cmd_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    with get_db() as conn:
        rows = conn.execute("SELECT id, company, status, deadline, contact, chat_id FROM briefs").fetchall()
    
    if not rows:
        await message.answer("📭 Локальная база пуста.")
        return
    
    text = "📋 Локальные записи:\n\n"
    for row in rows:
        linked = "✅" if row[5] else "❌"
        text += f"🆔 {row[0]}: {row[1]} — {row[2]} (до {row[3]}) — {row[4]} {linked}\n"
    await message.answer(text)

@dp.message(Command("set_status"))
async def cmd_set_status(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("📝 Формат: /set_status ID_записи Новый_статус")
        return
    
    try:
        record_id, new_status = int(args[1]), args[2]
        with get_db() as conn:
            conn.execute("UPDATE briefs SET status=? WHERE id=?", (new_status, record_id))
            conn.commit()
        await message.answer(f"✅ Статус записи {record_id} обновлён на: {new_status}")
    except ValueError:
        await message.answer("❌ ID должен быть числом")

@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("📝 Формат: /delete ID_записи")
        return
    
    try:
        record_id = int(args[1])
        with get_db() as conn:
            conn.execute("DELETE FROM briefs WHERE id=?", (record_id,))
            conn.commit()
        await message.answer(f"✅ Запись {record_id} удалена")
    except ValueError:
        await message.answer("❌ ID должен быть числом")

@dp.message(Command("link"))
async def cmd_link(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("📝 Формат: /link ID_записи Chat_ID")
        return
    
    try:
        record_id, chat_id = int(args[1]), int(args[2])
        with get_db() as conn:
            conn.execute("UPDATE briefs SET chat_id=? WHERE id=?", (chat_id, record_id))
            conn.commit()
        await message.answer(f"✅ Заказчик {chat_id} привязан к записи {record_id}")
    except ValueError:
        await message.answer("❌ ID и Chat_ID должны быть числами")

# ============= ЗАПУСК =============
async def main():
    init_db()
    print("🚀 Бот запущен! Нажми Ctrl+C для остановки.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
