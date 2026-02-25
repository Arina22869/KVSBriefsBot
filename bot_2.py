import logging
import sqlite3
from contextlib import contextmanager
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import asyncio

# ============= НАСТРОЙКИ =============
TOKEN = "8797047074:AAEHlaYsh26Jf-GsA4G54C-46AcSHTP_uMw"
OWNER_ID = 1665864236
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
                company TEXT PRIMARY KEY,
                chat_id INTEGER,
                status TEXT,
                deadline TEXT,
                contact TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        conn.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        conn.commit()

def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    with get_db() as conn:
        cursor = conn.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
        return cursor.fetchone() is not None

def add_admin(user_id):
    with get_db() as conn:
        conn.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (user_id,))
        conn.commit()

def remove_admin(user_id):
    if user_id == OWNER_ID:
        return False
    with get_db() as conn:
        conn.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        conn.commit()
        return True

def get_all_admins():
    with get_db() as conn:
        cursor = conn.execute('SELECT user_id FROM admins ORDER BY user_id')
        return [row[0] for row in cursor.fetchall()]

def get_brief_by_chat_id(chat_id):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT company, status, deadline, contact FROM briefs WHERE chat_id=?",
            (chat_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "company": row[0],
                "status": row[1],
                "deadline": row[2],
                "contact": row[3]
            }
        return None

def add_brief(company, deadline, contact):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO briefs (company, status, deadline, contact) VALUES (?, ?, ?, ?)",
            (company, "В работе", deadline, contact)
        )
        conn.commit()

def update_brief_status(company, new_status):
    with get_db() as conn:
        conn.execute(
            "UPDATE briefs SET status=? WHERE company=?",
            (new_status, company)
        )
        conn.commit()

def link_chat_to_brief(company, chat_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE briefs SET chat_id=? WHERE company=?",
            (chat_id, company)
        )
        conn.commit()

def get_all_briefs():
    with get_db() as conn:
        cursor = conn.execute("SELECT company, status, deadline, contact, chat_id FROM briefs")
        return cursor.fetchall()

def delete_brief(company):
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM briefs WHERE company=?", (company,))
        conn.commit()
        return cursor.rowcount > 0

# ============= КЛАВИАТУРА =============
def get_activists_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🔧 Команды активиста"))
    builder.add(KeyboardButton(text="📋 Список брифов"))
    builder.add(KeyboardButton(text="➕ Добавить бриф"))
    builder.add(KeyboardButton(text="❌ Удалить бриф"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# ============= КОМАНДЫ ЗАКАЗЧИКА =============
@dp.message(Command("start"))
async def cmd_start(message: Message):
    base_text = (
        f"👋 Привет, {message.from_user.full_name}!\n\n"
        "Я бот для отслеживания статуса твоего брифа.\n"
        "Если ты уже оставлял заявку — отправь /status"
    )
    
    if is_admin(message.from_user.id):
        base_text += (
            "\n\n🔧 Ты активист! Нажми /menu, чтобы открыть панель управления."
        )
    
    await message.answer(base_text)

@dp.message(Command("status"))
async def cmd_status(message: Message):
    chat_id = message.from_user.id
    brief = get_brief_by_chat_id(chat_id)
    
    if brief:
        text = (
            f"👤 Компания: {brief['company']}\n"
            f"📊 Статус: {brief['status']}\n"
            f"📅 Дедлайн: {brief['deadline']}\n"
            f"📞 Контакт: {brief['contact']}"
        )
    else:
        text = "❌ У тебя пока нет активных брифов."
    
    await message.answer(text)

# ============= МЕНЮ АКТИВИСТА =============
@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "🔧 Меню активиста:",
        reply_markup=get_activists_keyboard()
    )

@dp.message(lambda message: message.text == "🔧 Команды активиста")
async def show_commands(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    text = (
        "🔧 Команды активиста:\n\n"
        "📋 Управление брифами:\n"
        "/add Название Дедлайн Контакт – добавить бриф\n"
        "/set_status Название Новый статус – изменить статус\n"
        "/list – показать все брифы\n"
        "/delete Название – удалить бриф\n"
        "/link Название chat_id – привязать заказчика\n\n"
        "👑 Управление админами:\n"
        "/addadmin TelegramID – добавить админа\n"
        "/removeadmin TelegramID – удалить админа\n"
        "/listadmins – список админов"
    )
    await message.answer(text)

@dp.message(lambda message: message.text == "📋 Список брифов")
async def button_list(message: Message):
    await cmd_list(message)

@dp.message(lambda message: message.text == "➕ Добавить бриф")
async def button_add_prompt(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "➕ Чтобы добавить бриф, напиши:\n"
        "/add Название_компании Дедлайн Контакт\n\n"
        "Пример:\n"
        "/add ООО Пример 25.04.2024 @manager"
    )

@dp.message(lambda message: message.text == "❌ Удалить бриф")
async def button_delete_prompt(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "❌ Чтобы удалить бриф, напиши:\n"
        "/delete Название_компании\n\n"
        "Пример:\n"
        "/delete ООО Пример"
    )

# ============= КОМАНДЫ АДМИНОВ (БРИФЫ) =============
@dp.message(Command("add"))
async def cmd_add(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer(
            "📝 Формат: /add Название_компании Дедлайн Контакт\n"
            "Пример: /add ООО Пример 25.04.2024 @ivanov"
        )
        return
    
    company = args[1]
    deadline = args[2]
    contact = args[3]
    
    try:
        add_brief(company, deadline, contact)
        await message.answer(f"✅ Бриф для {company} добавлен! Статус: В работе")
    except sqlite3.IntegrityError:
        await message.answer(f"❌ Бриф для {company} уже существует")

@dp.message(Command("set_status"))
async def cmd_set_status(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer(
            "📝 Формат: /set_status Название_компании Новый статус\n"
            "Пример: /set_status ООО Пример На согласовании"
        )
        return
    
    company = args[1]
    new_status = args[2]
    
    update_brief_status(company, new_status)
    await message.answer(f"✅ Статус для {company} обновлён: {new_status}")

@dp.message(Command("list"))
async def cmd_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    briefs = get_all_briefs()
    if not briefs:
        await message.answer("📭 Пока нет ни одного брифа.")
        return
    
    text = "📋 Все брифы:\n\n"
    for company, status, deadline, contact, chat_id in briefs:
        linked = "✅" if chat_id and chat_id != 0 else "❌"
        text += f"• {company} {linked}\n  📊 {status}\n  📅 {deadline}\n  📞 {contact}\n\n"
    
    await message.answer(text)

@dp.message(Command("link"))
async def cmd_link(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer(
            "📝 Формат: /link Название_компании chat_id\n"
            "Пример: /link ООО Пример 123456789"
        )
        return
    
    company = args[1]
    try:
        chat_id = int(args[2])
        link_chat_to_brief(company, chat_id)
        await message.answer(f"✅ Заказчик привязан к брифу {company}")
    except ValueError:
        await message.answer("❌ chat_id должен быть числом")

@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📝 Формат: /delete Название_компании\n"
            "Пример: /delete ООО Пример"
        )
        return
    
    company = args[1]
    if delete_brief(company):
        await message.answer(f"✅ Бриф для {company} удалён")
    else:
        await message.answer(f"❌ Бриф с названием {company} не найден")

# ============= КОМАНДЫ УПРАВЛЕНИЯ АДМИНАМИ =============
@dp.message(Command("addadmin"))
async def cmd_add_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📝 Формат: /addadmin TelegramID\n"
            "Пример: /addadmin 123456789"
        )
        return
    
    try:
        new_admin_id = int(args[1])
        add_admin(new_admin_id)
        await message.answer(f"✅ Пользователь {new_admin_id} добавлен в админы")
    except ValueError:
        await message.answer("❌ ID должен быть числом")

@dp.message(Command("removeadmin"))
async def cmd_remove_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📝 Формат: /removeadmin TelegramID\n"
            "Пример: /removeadmin 123456789"
        )
        return
    
    try:
        admin_id = int(args[1])
        if remove_admin(admin_id):
            await message.answer(f"✅ Пользователь {admin_id} удалён из админов")
        else:
            await message.answer("❌ Владельца нельзя удалить или пользователь не найден")
    except ValueError:
        await message.answer("❌ ID должен быть числом")

@dp.message(Command("listadmins"))
async def cmd_list_admins(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    admins = get_all_admins()
    text = "👑 Список админов:\n\n"
    for admin_id in admins:
        if admin_id == OWNER_ID:
            text += f"• {admin_id} (владелец) 👑\n"
        else:
            text += f"• {admin_id}\n"
    
    await message.answer(text)

# ============= ЗАПУСК =============
async def main():
    init_db()
    print("🚀 Бот запущен! Нажми Ctrl+C для остановки.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
