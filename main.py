import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8681485490:AAHmWVJrzZ1O5R92HcXmG1QFdcE-Q95v8oM"
DATA_FILE = "data.json"
MAX_PLAYERS = 7
REMINDER_HOURS_BEFORE = 2

FIXED_COACH_ID = 7908057052  # ID тренера

PROFILE_NAME = 0
MATCH_DATE, MATCH_TIME, MATCH_LOCATION = range(3)

POSITIONS = [
    "Вратарь",
    "Правый Защитник",
    "Левый Защитник",
    "Полузащитник",
    "Правый Вингер",
    "Центральный Нападающий",
    "Левый Вингер"
]

# ==================== РАБОТА С ДАННЫМИ ====================
def load_data() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"players": {}, "team": {"players": [], "coach": None}, "matches": []}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_coach(user_id: int, data: dict) -> bool:
    if FIXED_COACH_ID is not None:
        return user_id == FIXED_COACH_ID
    return data["team"]["coach"] == user_id

def get_team_display(data: dict) -> str:
    team = data["team"]["players"]
    players = data["players"]
    if not team:
        return "Состав команды пуст."
    lines = []
    for idx, uid in enumerate(team, 1):
        p = players.get(str(uid), {})
        name = p.get("name", "Неизвестный")
        pos = p.get("position", "?")
        lines.append(f"{idx}. {name} – {pos}")
    return "🧑‍🤝‍🧑 Текущий состав:\n" + "\n".join(lines)

def get_future_matches(data: dict) -> List[dict]:
    now = datetime.now()
    future = [m for m in data["matches"] if datetime.fromisoformat(m["datetime"]) > now]
    future.sort(key=lambda m: m["datetime"])
    return future

def format_match(match: dict) -> str:
    dt = datetime.fromisoformat(match["datetime"]).strftime("%d.%m.%Y %H:%M")
    return (
        f"📅 {dt}\n"
        f"📍 {match['location']}"
    )

def find_player_by_name(data: dict, name: str) -> Optional[str]:
    for uid, p in data["players"].items():
        if p.get("name") == name:
            return uid
    return None

# ==================== КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "⚽️ Бот мини-футбольной команды\n\n"
        "Доступные команды:\n"
        "/profile — создать/посмотреть профиль (для Telegram-пользователей)\n"
        "/team — состав команды\n"
        "/add_player @user — добавить игрока с Telegram-аккаунтом (тренер)\n"
        "/add_player Имя Позиция — добавить игрока вручную (тренер)\n"
        "/match — создать матч\n"
        "/matches — список будущих матчей\n"
        "/setcoach @ник — назначить тренера (тренер)\n"
        "/setplayer @name/Имя Позиция — назначить/изменить позицию (тренер)\n\n"
        f"Позиции: {', '.join(POSITIONS)}\n"
        "Тренер зафиксирован. Сначала создайте профиль через /profile, если вы играете."
    )
    await update.message.reply_text(help_text)

# -------------------- ПРОФИЛЬ --------------------
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = update.effective_user.id
    if str(user_id) in data["players"]:
        p = data["players"][str(user_id)]
        text = (
            f"Ваш профиль:\n"
            f"Имя: {p['name']}\n"
            f"Позиция: {p.get('position', 'не назначена тренером')}\n"
            f"Контакт: @{p['contact']}"
        )
        await update.message.reply_text(text)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Введите ваше имя / ник:")
        return PROFILE_NAME

async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user = update.effective_user
    data = load_data()
    data["players"][str(user.id)] = {
        "name": name,
        "position": None,
        "contact": user.username or f"id{user.id}"
    }
    save_data(data)
    await update.message.reply_text(
        "✅ Профиль сохранён!\nПозицию назначит тренер командой /setplayer @username или /setplayer ВашеИмя Позиция",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def profile_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание профиля отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# -------------------- ДОБАВЛЕНИЕ ИГРОКА --------------------
async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    if not is_coach(user_id, data):
        await update.message.reply_text("❌ Только тренер может добавлять игроков.")
        return
    if not context.args:
        await update.message.reply_text(
            "Использование:\n"
            "/add_player @user – добавить игрока с Telegram\n"
            "/add_player Имя Позиция – добавить игрока вручную\n"
            f"Допустимые позиции: {', '.join(POSITIONS)}\n"
            "Пример: /add_player @ivan или /add_player Хонор Полузащитник"
        )
        return
    # Первый вход
    if not data["team"]["players"]:
        if FIXED_COACH_ID is not None and user_id != FIXED_COACH_ID:
            await update.message.reply_text("❌ Только зафиксированный тренер может создать команду.")
            return
        if str(user_id) not in data["players"]:
            await update.message.reply_text("Сначала создайте профиль через /profile")
            return
        data["team"]["players"].append(user_id)
        if FIXED_COACH_ID is not None:
            data["team"]["coach"] = FIXED_COACH_ID
        else:
            data["team"]["coach"] = user_id
        save_data(data)
        await update.message.reply_text("✅ Вы добавлены в команду и стали тренером! 🧑‍🏫")
        return
    # Обычное добавление
    first_arg = context.args[0]
    if first_arg.startswith("@"):
        username = first_arg.lstrip("@")
        target_id = None
        for uid, p in data["players"].items():
            if p.get("contact") == username:
                target_id = int(uid)
                break
        if target_id is None:
            await update.message.reply_text(f"Игрок @{username} не найден. Сначала он должен создать профиль через /profile.")
            return
        if len(data["team"]["players"]) >= MAX_PLAYERS:
            await update.message.reply_text(f"Команда уже укомплектована (максимум {MAX_PLAYERS} игроков).")
            return
        if target_id in data["team"]["players"]:
            await update.message.reply_text("Этот игрок уже в команде.")
            return
        data["team"]["players"].append(target_id)
        save_data(data)
        await update.message.reply_text(f"Игрок @{username} добавлен в команду!")
    else:
        if len(context.args) < 2:
            await update.message.reply_text("Укажите имя и позицию: /add_player Имя Позиция")
            return
        name = context.args[0]
        pos_input = " ".join(context.args[1:])
        if pos_input not in POSITIONS:
            await update.message.reply_text(f"Неверная позиция. Допустимые: {', '.join(POSITIONS)}")
            return
        if len(data["team"]["players"]) >= MAX_PLAYERS:
            await update.message.reply_text(f"Команда уже укомплектована (максимум {MAX_PLAYERS} игроков).")
            return
        new_id = f"manual_{uuid.uuid4().hex[:8]}"
        data["players"][new_id] = {
            "name": name,
            "position": pos_input,
            "contact": None
        }
        data["team"]["players"].append(new_id)
        save_data(data)
        await update.message.reply_text(f"✅ Игрок «{name}» ({pos_input}) добавлен в команду вручную.")

# -------------------- НАЗНАЧЕНИЕ ПОЗИЦИИ --------------------
async def setplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    if not is_coach(user_id, data):
        await update.message.reply_text("❌ Только тренер может назначать позицию.")
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Использование:\n"
            "/setplayer @username Позиция – для игрока с Telegram\n"
            "/setplayer Имя Позиция – для игрока, добавленного вручную\n"
            f"Допустимые позиции: {', '.join(POSITIONS)}\n"
            "Пример: /setplayer @ivan Правый Защитник или /setplayer Алексей Левый Вингер"
        )
        return
    identifier = context.args[0]
    pos_input = " ".join(context.args[1:])
    if pos_input not in POSITIONS:
        await update.message.reply_text(f"Неверная позиция. Допустимые: {', '.join(POSITIONS)}")
        return
    target_uid = None
    if identifier.startswith("@"):
        username = identifier.lstrip("@")
        for uid, p in data["players"].items():
            if p.get("contact") == username:
                target_uid = uid
                break
    else:
        target_uid = find_player_by_name(data, identifier)
    if target_uid is None:
        await update.message.reply_text(f"Игрок «{identifier}» не найден.")
        return
    data["players"][target_uid]["position"] = pos_input
    save_data(data)
    await update.message.reply_text(f"✅ Игроку {identifier} назначена позиция «{pos_input}».")

# -------------------- СОСТАВ --------------------
async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    text = get_team_display(data)
    coach_id = FIXED_COACH_ID or data["team"]["coach"]
    if coach_id:
        coach_info = data["players"].get(str(coach_id), {})
        coach_name = coach_info.get("name", "Неизвестный")
        text += f"\n\n🧑‍🏫 Тренер: {coach_name}"
    await update.message.reply_text(text)

# -------------------- МАТЧ (создание) --------------------
async def match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите дату матча в формате ДД.ММ.ГГГГ:")
    return MATCH_DATE

async def match_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = update.message.text.strip()
    try:
        datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        await update.message.reply_text("Неверный формат. Используйте ДД.ММ.ГГГГ")
        return MATCH_DATE
    context.user_data["match_date"] = date_str
    await update.message.reply_text("Введите время матча в формате ЧЧ:ММ:")
    return MATCH_TIME

async def match_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_str = update.message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Используйте ЧЧ:ММ")
        return MATCH_TIME
    context.user_data["match_time"] = time_str
    await update.message.reply_text("Введите место проведения матча:")
    return MATCH_LOCATION

async def match_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.text.strip()
    date_str = context.user_data["match_date"]
    time_str = context.user_data["match_time"]
    dt_str = f"{date_str} {time_str}"
    dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
    data = load_data()
    match = {
        "datetime": dt.isoformat(),
        "location": location,
        "participants": {}  # больше не используется, но оставим для совместимости
    }
    data["matches"].append(match)
    save_data(data)
    await update.message.reply_text(
        f"✅ Матч создан!\n"
        f"📅 {date_str} в {time_str}\n"
        f"📍 {location}\n\n"
        f"Список матчей: /matches"
    )
    return ConversationHandler.END

async def match_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание матча отменено.")
    return ConversationHandler.END

# -------------------- СПИСОК МАТЧЕЙ (без участников) --------------------
async def matches_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    future = get_future_matches(data)
    if not future:
        await update.message.reply_text("Нет предстоящих матчей.")
        return
    lines = ["📋 **Предстоящие матчи:**"]
    for idx, match in enumerate(future, 1):
        lines.append(f"\n{idx}. {format_match(match)}")
    await update.message.reply_text("\n".join(lines))

# -------------------- НАЗНАЧЕНИЕ ТРЕНЕРА --------------------
async def setcoach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    if FIXED_COACH_ID is not None:
        await update.message.reply_text("❌ Тренер зафиксирован и не может быть изменён.")
        return
    if not is_coach(user_id, data):
        await update.message.reply_text("❌ Только тренер может передать полномочия.")
        return
    if not context.args:
        await update.message.reply_text("Укажите @username нового тренера: /setcoach @user")
        return
    username = context.args[0].lstrip("@")
    target_id = None
    for uid, p in data["players"].items():
        if p.get("contact") == username:
            target_id = int(uid)
            break
    if target_id is None or target_id not in data["team"]["players"]:
        await update.message.reply_text("Игрок не найден или не состоит в команде.")
        return
    data["team"]["coach"] = target_id
    save_data(data)
    await update.message.reply_text(f"🧑‍🏫 Тренер теперь @{username}")

# ==================== УВЕДОМЛЕНИЯ (только для тренера) ====================
async def check_matches_callback(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now()
    for match in data["matches"]:
        dt = datetime.fromisoformat(match["datetime"])
        if dt > now:
            if now + timedelta(hours=REMINDER_HOURS_BEFORE) >= dt > now:
                coach_id = FIXED_COACH_ID or data["team"]["coach"]
                if coach_id:
                    try:
                        await context.bot.send_message(
                            chat_id=coach_id,
                            text=f"⏰ Напоминание: матч через {REMINDER_HOURS_BEFORE} ч.!\n{format_match(match)}"
                        )
                    except Exception as e:
                        logging.warning(f"Не удалось отправить напоминание тренеру: {e}")

# ==================== MAIN ====================
def main():
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()

    profile_handler = ConversationHandler(
        entry_points=[CommandHandler("profile", profile_start)],
        states={
            PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name)],
        },
        fallbacks=[CommandHandler("cancel", profile_cancel)],
    )

    match_handler = ConversationHandler(
        entry_points=[CommandHandler("match", match_start)],
        states={
            MATCH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_date)],
            MATCH_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_time)],
            MATCH_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_location)],
        },
        fallbacks=[CommandHandler("cancel", match_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(profile_handler)
    app.add_handler(match_handler)
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("add_player", add_player))
    app.add_handler(CommandHandler("matches", matches_list))
    app.add_handler(CommandHandler("setcoach", setcoach))
    app.add_handler(CommandHandler("setplayer", setplayer))

    # Уведомления только тренеру о предстоящем матче
    job_queue = app.job_queue
    job_queue.run_repeating(check_matches_callback, interval=600, first=10)

    print("🚀 Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
