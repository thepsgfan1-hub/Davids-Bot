```python
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

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
BOT_TOKEN = "8681485490:AAFKT4Qbj52JnQ9LzICRD1fwWwMvC7JP90Q"
DATA_FILE = "data.json"
MAX_PLAYERS = 7
REMINDER_HOURS_BEFORE = 2

FIXED_COACH_ID = "7908057052"  # теперь строка

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

# ==================== DATA ====================
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"players": {}, "team": {"players": [], "coach": None}, "matches": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_coach(user_id: int, data):
    return str(user_id) == FIXED_COACH_ID

def get_team_display(data):
    team = data["team"]["players"]
    players = data["players"]

    if not team:
        return "Состав пуст."

    lines = []
    for i, uid in enumerate(team, 1):
        p = players.get(uid, {})
        lines.append(f"{i}. {p.get('name','?')} – {p.get('position','?')}")

    return "🧑‍🤝‍🧑 Состав:\n" + "\n".join(lines)

def get_future_matches(data):
    now = datetime.now()
    return sorted(
        [m for m in data["matches"] if datetime.fromisoformat(m["datetime"]) > now],
        key=lambda x: x["datetime"]
    )

def format_match(m):
    dt = datetime.fromisoformat(m["datetime"]).strftime("%d.%m.%Y %H:%M")
    return f"📅 {dt}\n📍 {m['location']}"

def find_player_by_name(data, name) -> Optional[str]:
    for uid, p in data["players"].items():
        if p.get("name") == name:
            return uid
    return None

# ==================== COMMANDS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚽️ Бот команды\n/profile\n/team\n/match\n/matches")

# -------- PROFILE --------
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = str(update.effective_user.id)

    if uid in data["players"]:
        p = data["players"][uid]
        await update.message.reply_text(f"{p['name']} | {p.get('position')}")
        return ConversationHandler.END

    await update.message.reply_text("Введите имя:")
    return PROFILE_NAME

async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = update.effective_user

    data["players"][str(user.id)] = {
        "name": update.message.text,
        "position": None,
        "contact": user.username
    }

    save_data(data)
    await update.message.reply_text("Готово")
    return ConversationHandler.END

# -------- TEAM --------
async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    await update.message.reply_text(get_team_display(data))

# -------- ADD PLAYER --------
async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    if not is_coach(update.effective_user.id, data):
        await update.message.reply_text("❌ Только тренер")
        return

    if not context.args:
        return

    name = context.args[0]
    pos = " ".join(context.args[1:])

    if pos not in POSITIONS:
        await update.message.reply_text("Неверная позиция")
        return

    uid = f"manual_{uuid.uuid4().hex[:6]}"

    data["players"][uid] = {"name": name, "position": pos}
    data["team"]["players"].append(uid)

    save_data(data)
    await update.message.reply_text("Добавлен")

# -------- MATCH --------
async def match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    if not is_coach(update.effective_user.id, data):
        await update.message.reply_text("❌ Только тренер")
        return ConversationHandler.END

    await update.message.reply_text("Дата ДД.ММ.ГГГГ")
    return MATCH_DATE

async def match_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text
    await update.message.reply_text("Время ЧЧ:ММ")
    return MATCH_TIME

async def match_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["time"] = update.message.text
    await update.message.reply_text("Место")
    return MATCH_LOCATION

async def match_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    dt = datetime.strptime(
        context.user_data["date"] + " " + context.user_data["time"],
        "%d.%m.%Y %H:%M"
    )

    data["matches"].append({
        "datetime": dt.isoformat(),
        "location": update.message.text,
        "reminded": False
    })

    save_data(data)
    await update.message.reply_text("Матч создан")
    return ConversationHandler.END

# -------- MATCHES --------
async def matches_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    matches = get_future_matches(data)

    if not matches:
        await update.message.reply_text("Нет матчей")
        return

    text = "\n\n".join(format_match(m) for m in matches)
    await update.message.reply_text(text)

# -------- REMINDER --------
async def check_matches_callback(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now()
    changed = False

    for m in data["matches"]:
        dt = datetime.fromisoformat(m["datetime"])

        if dt > now and not m.get("reminded"):
            if now + timedelta(hours=REMINDER_HOURS_BEFORE) >= dt:
                await context.bot.send_message(
                    chat_id=int(FIXED_COACH_ID),
                    text=f"⏰ Скоро матч!\n{format_match(m)}"
                )
                m["reminded"] = True
                changed = True

    if changed:
        save_data(data)

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    profile = ConversationHandler(
        entry_points=[CommandHandler("profile", profile_start)],
        states={PROFILE_NAME: [MessageHandler(filters.TEXT, profile_name)]},
        fallbacks=[]
    )

    match = ConversationHandler(
        entry_points=[CommandHandler("match", match_start)],
        states={
            MATCH_DATE: [MessageHandler(filters.TEXT, match_date)],
            MATCH_TIME: [MessageHandler(filters.TEXT, match_time)],
            MATCH_LOCATION: [MessageHandler(filters.TEXT, match_location)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(profile)
    app.add_handler(match)
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("add_player", add_player))
    app.add_handler(CommandHandler("matches", matches_list))

    app.job_queue.run_repeating(check_matches_callback, interval=600)

    print("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
```
