import telebot
from telebot import types
import random
import time
import json
import os

# --- [1] КОНФИГУРАЦИЯ ---
TOKEN = "8681485490:AAHmWVJrzZ1O5R92HcXmG1QFdcE-Q95v8oM"

ADMINS = ["verybigsun"] 
bot = telebot.TeleBot(TOKEN)

# Настройка КД (в секундах). 3600 сек = 1 час.
COOLDOWN_TIME = 3600 

FILES = {'cards': 'cards_data.json', 'colls': 'collections_data.json', 'users': 'users_stats.json'}

# Очки за рейтинг звезд
STATS = {
    1: {"score": 1000},
    2: {"score": 2000},
    3: {"score": 4000},
    4: {"score": 6000},
    5: {"score": 10000}
}

# Словарь для хранения времени последней попытки
last_roll = {}

# --- [2] БД ФУНКЦИИ ---
def load_db(key):
    if not os.path.exists(FILES[key]):
        res = {} if key in ['users', 'colls'] else []
        save_db(res, key)
        return res
    with open(FILES[key], 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return {} if key in ['users', 'colls'] else []

def save_db(data, key):
    with open(FILES[key], 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_stars(count):
    try:
        return "⭐" * int(count)
    except:
        return "⭐"

# --- [3] КЛАВИАТУРЫ ---
def main_kb(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Убрали значок, оставили только текст
    markup.row("Получить карту", "🗂 Коллекция")
    markup.row("👤 Профиль", "🏆 Топ игроков")
    markup.row("💎 Премиум")
    if user.username and user.username.lower() in [a.lower() for a in ADMINS]:
        markup.add("🛠 Админ-панель")
    return markup

# --- [4] ЛОГИКА ИГРЫ ---

@bot.message_handler(commands=['start'])
def start(m):
    uid = str(m.from_user.id)
    users = load_db('users')
    if uid not in users:
        users[uid] = {"score": 0, "username": m.from_user.username or f"user_{uid}"}
        save_db(users, 'users')
    
    bot.send_message(m.chat.id, "👋 Привет! Это бот СЛС карточек.", 
                     reply_markup=main_kb(m.from_user), parse_mode="Markdown")

# Обработка нажатия кнопки ИЛИ написания текста "Получить карту" (в личке или группе)
@bot.message_handler(func=lambda m: m.text == "Получить карту")
def roll(m):
    uid = str(m.from_user.id)
    username = m.from_user.username or ""
    is_admin = username.lower() in [a.lower() for a in ADMINS]

    # ПРОВЕРКА КД (Админы игнорируют)
    if not is_admin:
        now = time.time()
        if uid in last_roll:
            elapsed = now - last_roll[uid]
            if elapsed < COOLDOWN_TIME:
                remains = int(COOLDOWN_TIME - elapsed)
                mins = remains // 60
                secs = remains % 60
                return bot.send_message(m.chat.id, f"⏳ Нужно подождать еще **{mins} мин. {secs} сек.**", parse_mode="Markdown")
        
        last_roll[uid] = now

    cards = load_db('cards')
    users = load_db('users')
    colls = load_db('colls')

    if not cards: 
        return bot.send_message(m.chat.id, "❌ В игре пока нет карточек!")

    won = random.choice(cards)
    if uid not in colls: colls[uid] = []
    
    is_new = not any(c['name'] == won['name'] for c in colls[uid])
    base_pts = STATS.get(int(won.get('stars', 1)), {"score": 500})["score"]
    added_pts = base_pts if is_new else int(base_pts * 0.3)
    
    # Убедимся, что пользователь есть в базе
    if uid not in users:
        users[uid] = {"score": 0, "username": m.from_user.username or f"user_{uid}"}

    users[uid]['score'] += int(added_pts)
    if is_new:
        colls[uid].append(won)
        save_db(colls, 'colls')
    save_db(users, 'users')

    status = "🆕 Новая карта!" if is_new else "♻️ Повторка"
    
    caption = (
        f"⚽️ **{won['name']}** ({status})\n"
        f" — — — — — — — — — —\n"
        f"🎯 **Позиция:** `{won.get('pos', '—')}`\n"
        f"📊 **Рейтинг:** {get_stars(won.get('stars', 1))}\n"
        f" — — — — — — — — — —\n"
        f"💠 **Очки:** `+{int(added_pts):,}` | Всего: `{users[uid]['score']:,}`"
    )

    try:
        bot.send_photo(m.chat.id, won['photo'], caption=caption, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Ошибка при отправке фото: {e}\n\n{caption}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🏆 Топ игроков")
def top_players(m):
    users = load_db('users')
    sorted_users = sorted(users.items(), key=lambda x: x[1]['score'], reverse=True)
    
    text = "🏆 **ТОП-10 ИГРОКОВ:**\n\n"
    for i, (uid, data) in enumerate(sorted_users[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} @{data['username']} — `{data['score']:,}` очков\n"
    
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🗂 Коллекция")
def my_collection(m):
    uid = str(m.from_user.id)
    colls = load_db('colls')
    my_cards = colls.get(uid, [])
    
    if not my_cards:
        return bot.send_message(m.chat.id, "🗂 Ваша коллекция пока пуста!")
    
    text = f"🗂 **ВАША КОЛЛЕКЦИЯ ({len(my_cards)} шт.):**\n\n"
    for card in my_cards:
        text += f"• {card['name']} ({get_stars(card.get('stars', 1))})\n"
    
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(m):
    uid = str(m.from_user.id)
    u = load_db('users').get(uid, {"score": 0})
    c = len(load_db('colls').get(uid, []))
    
    text = (
        f"👤 **ВАШ ПРОФИЛЬ**\n"
        f" — — — — — — — —\n"
        f"🆔 ID: `{uid}`\n"
        f"💠 Очки: `{u['score']:,}`\n"
        f"🗂 Коллекция: `{c}` шт.\n"
        f" — — — — — — — —"
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💎 Премиум")
def prem(m):
    bot.send_message(m.chat.id, "💎 **Премиум статус**\n\n• Крутки без КД\n✉️ Купить: @verybigsun", parse_mode="Markdown")

# --- [5] АДМИН-ПАНЕЛЬ ---

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель")
def adm(m):
    if m.from_user.username and m.from_user.username.lower() in [a.lower() for a in ADMINS]:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("➕ Добавить карту", "🗑 Удалить карту")
        markup.row("🏠 Назад в меню")
        bot.send_message(m.chat.id, "🛠 Панель управления администратора:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🗑 Удалить карту")
def delete_menu(m):
    if m.from_user.username and m.from_user.username.lower() in [a.lower() for a in ADMINS]:
        cards = load_db('cards')
        if not cards:
            return bot.send_message(m.chat.id, "❌ База карт пуста.")
        
        markup = types.InlineKeyboardMarkup()
        for c in cards:
            markup.add(types.InlineKeyboardButton(f"❌ Удалить {c['name']}", callback_data=f"del_{c['name']}"))
        
        bot.send_message(m.chat.id, "Выберите карту для удаления:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def process_delete(call):
    name_to_delete = call.data.replace("del_", "")
    cards = load_db('cards')
    new_cards = [c for c in cards if c['name'] != name_to_delete]
    save_db(new_cards, 'cards')
    bot.edit_message_text(f"✅ Карта **{name_to_delete}** удалена.", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту")
def add_start(m):
    if m.from_user.username and m.from_user.username.lower() in [a.lower() for a in ADMINS]:
        msg = bot.send_message(m.chat.id, "Введите ИМЯ игрока:")
        bot.register_next_step_handler(msg, add_step_stars)

def add_step_stars(m):
    name = m.text
    msg = bot.send_message(m.chat.id, f"Введите РЕЙТИНГ (1-5) для {name}:")
    bot.register_next_step_handler(msg, add_step_pos, name)

def add_step_pos(m, name):
    stars = m.text
    msg = bot.send_message(m.chat.id, f"Введите ПОЗИЦИЮ:")
    bot.register_next_step_handler(msg, add_step_photo, name, stars)

def add_step_photo(m, name, stars):
    pos = m.text
    msg = bot.send_message(m.chat.id, f"Отправьте ФОТО:")
    bot.register_next_step_handler(msg, add_final, name, stars, pos)

def add_final(m, name, stars, pos):
    if not m.photo:
        return bot.send_message(m.chat.id, "❌ Нужно фото!")
    cards = load_db('cards')
    cards.append({
        "name": name, 
        "stars": int(stars) if stars.isdigit() else 1, 
        "pos": pos, 
        "photo": m.photo[-1].file_id
    })
    save_db(cards, 'cards')
    bot.send_message(m.chat.id, f"✅ Карта {name} успешно добавлена!", reply_markup=main_kb(m.from_user))

@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def back(m):
    bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_kb(m.from_user))

if __name__ == '__main__':
    print("Бот запущен и готов к работе!")
    bot.infinity_polling()
