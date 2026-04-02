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

# КД в секундах (3600 = 1 час)
COOLDOWN_TIME = 3600 

FILES = {
    'cards': 'cards_data.json', 
    'colls': 'collections_data.json', 
    'users': 'users_stats.json',
    'lineups': 'lineup_data.json'
}

# Настройка очков за звезды
STATS = {
    1: {"score": 1000},
    2: {"score": 2000},
    3: {"score": 4000},
    4: {"score": 6000},
    5: {"score": 10000}
}

# Список позиций для состава
POSITIONS = ["КФ", "ПВ", "ЛВ", "ЦП", "ПЗ", "ЛЗ", "ГК"]

# Словарь для хранения времени последнего получения карты
last_roll = {}

# --- [2] ФУНКЦИИ РАБОТЫ С БАЗОЙ ДАННЫХ ---

def load_db(key):
    """Загрузка данных из JSON файла"""
    if not os.path.exists(FILES[key]):
        # Если файла нет, создаем пустой объект или список
        if key == 'cards':
            res = []
        else:
            res = {}
        save_db(res, key)
        return res
    
    with open(FILES[key], 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return [] if key == 'cards' else {}

def save_db(data, key):
    """Сохранение данных в JSON файл"""
    with open(FILES[key], 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_stars(count):
    """Преобразование числа в строку со звездами"""
    try:
        return "⭐" * int(count)
    except:
        return "⭐"

# --- [3] КЛАВИАТУРЫ ---

def main_kb(user):
    """Главное меню бота"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Кнопка без значка, как ты просил
    markup.row("Получить карту", "🗂 Коллекция")
    markup.row("🏟 Мой состав", "🏆 Топ игроков")
    markup.row("👤 Профиль", "💎 Премиум")
    
    # Проверка на админа для отображения панели
    if user.username and user.username.lower() in [a.lower() for a in ADMINS]:
        markup.add("🛠 Админ-панель")
    return markup

def lineup_kb(uid):
    """Клавиатура для управления составом"""
    lineups = load_db('lineups')
    user_lineup = lineups.get(str(uid), {})
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for pos in POSITIONS:
        # Если позиция занята — пишем имя игрока, если нет — "Пусто"
        player_name = user_lineup.get(pos, "Пусто")
        markup.add(types.InlineKeyboardButton(
            text=f"{pos}: {player_name}", 
            callback_data=f"setpos_{pos}"
        ))
    return markup

# --- [4] ОСНОВНАЯ ЛОГИКА ---

@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = str(m.from_user.id)
    users = load_db('users')
    
    if uid not in users:
        users[uid] = {
            "score": 0, 
            "username": m.from_user.username or f"user_{uid}"
        }
        save_db(users, 'users')
    
    bot.send_message(
        m.chat.id, 
        "👋 Привет! Это бот СЛС карточек.\nИспользуй кнопки ниже или напиши 'Получить карту' в группе.", 
        reply_markup=main_kb(m.from_user)
    )

@bot.message_handler(func=lambda m: m.text == "Получить карту")
def roll_card(m):
    uid = str(m.from_user.id)
    username = m.from_user.username or ""
    is_admin = username.lower() in [a.lower() for a in ADMINS]

    # Проверка КД (Админы игнорируют задержку)
    if not is_admin:
        now = time.time()
        if uid in last_roll:
            elapsed = now - last_roll[uid]
            if elapsed < COOLDOWN_TIME:
                remains = int(COOLDOWN_TIME - elapsed)
                mins = remains // 60
                secs = remains % 60
                return bot.send_message(
                    m.chat.id, 
                    f"⏳ Нужно подождать еще **{mins} мин. {secs} сек.**", 
                    parse_mode="Markdown"
                )
        last_roll[uid] = now

    cards = load_db('cards')
    users = load_db('users')
    colls = load_db('colls')

    if not cards:
        return bot.send_message(m.chat.id, "❌ В базе еще нет карточек! Добавь их через админку.")

    # Выбираем случайную карту
    won_card = random.choice(cards)
    
    if uid not in colls:
        colls[uid] = []
    
    # Проверка на новую карту в коллекции
    is_new = not any(c['name'] == won_card['name'] for c in colls[uid])
    
    # Начисление очков
    stars_count = int(won_card.get('stars', 1))
    base_points = STATS.get(stars_count, {"score": 500})["score"]
    
    # За повторку даем 30% очков
    final_points = base_points if is_new else int(base_points * 0.3)
    
    if uid not in users:
        users[uid] = {"score": 0, "username": username}
    
    users[uid]['score'] += int(final_points)
    
    if is_new:
        colls[uid].append(won_card)
        save_db(colls, 'colls')
    
    save_db(users, 'users')

    status_text = "🆕 Новая карта!" if is_new else "♻️ Повторка"
    
    caption = (
        f"⚽️ **{won_card['name']}** ({status_text})\n"
        f" — — — — — — — — — —\n"
        f"🎯 Позиция: `{won_card.get('pos', '—')}`\n"
        f"📊 Рейтинг: {get_stars(won_card.get('stars', 1))}\n"
        f" — — — — — — — — — —\n"
        f"💠 Очки: `+{int(final_points):,}` | Всего: `{users[uid]['score']:,}`"
    )

    try:
        bot.send_photo(m.chat.id, won_card['photo'], caption=caption, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(m.chat.id, f"⚠️ Ошибка фото: {e}\n\n{caption}", parse_mode="Markdown")

# --- ФУНКЦИИ ТОПА И ПРОФИЛЯ ---

@bot.message_handler(func=lambda m: m.text == "🏆 Топ игроков")
def show_top(m):
    users = load_db('users')
    
    # Сортировка по очкам (score)
    # x[1] — это данные пользователя, .get('score', 0) — вытягиваем очки
    sorted_list = sorted(users.items(), key=lambda x: x[1].get('score', 0), reverse=True)
    
    top_text = "🏆 **ТОП-10 ИГРОКОВ ПО ОЧКАМ:**\n\n"
    
    for i, (uid, data) in enumerate(sorted_list[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        user_display = data.get('username', f"ID:{uid}")
        user_score = data.get('score', 0)
        top_text += f"{medal} @{user_display} — `{user_score:,}` очков\n"
    
    bot.send_message(m.chat.id, top_text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def show_profile(m):
    uid = str(m.from_user.id)
    users = load_db('users')
    colls = load_db('colls')
    
    u_data = users.get(uid, {"score": 0, "username": "Неизвестно"})
    u_cards = len(colls.get(uid, []))
    
    profile_text = (
        f"👤 **ВАШ ПРОФИЛЬ**\n"
        f" — — — — — — — —\n"
        f"🆔 ID: `{uid}`\n"
        f"💠 Очки: `{u_data['score']:,}`\n"
        f"🗂 Карт в коллекции: `{u_cards}`\n"
        f" — — — — — — — —"
    )
    bot.send_message(m.chat.id, profile_text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🗂 Коллекция")
def show_collection(m):
    uid = str(m.from_user.id)
    colls = load_db('colls')
    my_cards = colls.get(uid, [])
    
    if not my_cards:
        return bot.send_message(m.chat.id, "🗂 Твоя коллекция пока пуста. Получи свою первую карту!")
    
    # Группируем список имен
    names = [f"• {c['name']} ({get_stars(c['stars'])})" for c in my_cards]
    full_list = "\n".join(names)
    
    # Если список слишком длинный, Telegram может выдать ошибку, поэтому ограничим
    if len(full_list) > 4000:
        full_list = full_list[:4000] + "\n...и другие"

    bot.send_message(m.chat.id, f"🗂 **ТВОЯ КОЛЛЕКЦИЯ ({len(my_cards)} шт.):**\n\n{full_list}", parse_mode="Markdown")

# --- [5] МОЙ СОСТАВ (7 ПОЗИЦИЙ) ---

@bot.message_handler(func=lambda m: m.text == "🏟 Мой состав")
def show_lineup(m):
    bot.send_message(
        m.chat.id, 
        "🏟 **Управление составом**\nНажми на позицию, чтобы поставить туда игрока из твоей коллекции.",
        reply_markup=lineup_kb(m.from_user.id)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("setpos_"))
def handle_set_position(call):
    pos = call.data.split("_")[1]
    uid = str(call.from_user.id)
    colls = load_db('colls')
    my_cards = colls.get(uid, [])
    
    if not my_cards:
        return bot.answer_callback_query(call.id, "❌ У тебя нет игроков в коллекции!", show_alert=True)
    
    # Создаем кнопки с именами игроков из коллекции
    markup = types.InlineKeyboardMarkup()
    for card in my_cards:
        markup.add(types.InlineKeyboardButton(
            text=f"{card['name']} ({card.get('pos', '—')})", 
            callback_data=f"savepos_{pos}_{card['name']}"
        ))
    
    # Кнопка отмены
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_lineup"))
    
    bot.edit_message_text(
        text=f"Выбери игрока на позицию **{pos}**:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("savepos_"))
def handle_save_position(call):
    # Данные приходят в формате savepos_ПОЗИЦИЯ_ИМЯ
    data = call.data.split("_")
    pos = data[1]
    player_name = data[2]
    uid = str(call.from_user.id)
    
    lineups = load_db('lineups')
    
    if uid not in lineups:
        lineups[uid] = {}
    
    # Сохраняем игрока на позицию
    lineups[uid][pos] = player_name
    save_db(lineups, 'lineups')
    
    bot.answer_callback_query(call.id, f"✅ {player_name} поставлен на {pos}")
    
    # Возвращаемся в меню состава
    bot.edit_message_text(
        text="🏟 **Состав обновлен!**",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=lineup_kb(uid)
    )

@bot.callback_query_handler(func=lambda c: c.data == "back_to_lineup")
def handle_back_lineup(call):
    bot.edit_message_text(
        text="🏟 **Управление составом**",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=lineup_kb(call.from_user.id)
    )

# --- [6] АДМИН-ПАНЕЛЬ ---

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель")
def admin_panel(m):
    username = m.from_user.username or ""
    if username.lower() in [a.lower() for a in ADMINS]:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("➕ Добавить карту", "🗑 Удалить карту")
        markup.row("🏠 Назад в меню")
        bot.send_message(m.chat.id, "🛠 Режим администратора включен:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту")
def admin_add_name(m):
    username = m.from_user.username or ""
    if username.lower() in [a.lower() for a in ADMINS]:
        msg = bot.send_message(m.chat.id, "1. Введите ИМЯ игрока:")
        bot.register_next_step_handler(msg, admin_add_stars)

def admin_add_stars(m):
    player_name = m.text
    msg = bot.send_message(m.chat.id, f"2. Введите РЕЙТИНГ (число от 1 до 5) для {player_name}:")
    bot.register_next_step_handler(msg, admin_add_pos, player_name)

def admin_add_pos(m, player_name):
    stars = m.text
    msg = bot.send_message(m.chat.id, f"3. Введите ПОЗИЦИЮ (напр. ГК, КФ) для {player_name}:")
    bot.register_next_step_handler(msg, admin_add_photo, player_name, stars)

def admin_add_photo(m, player_name, stars):
    pos = m.text
    msg = bot.send_message(m.chat.id, f"4. Отправьте ФОТО для игрока {player_name}:")
    bot.register_next_step_handler(msg, admin_add_final, player_name, stars, pos)

def admin_add_final(m, player_name, stars, pos):
    if not m.photo:
        return bot.send_message(m.chat.id, "❌ Это не фото! Попробуй снова через меню.")
    
    cards = load_db('cards')
    new_card = {
        "name": player_name,
        "stars": int(stars) if stars.isdigit() else 1,
        "pos": pos,
        "photo": m.photo[-1].file_id
    }
    cards.append(new_card)
    save_db(cards, 'cards')
    
    bot.send_message(m.chat.id, f"✅ Игрок {player_name} успешно добавлен!", reply_markup=main_kb(m.from_user))

@bot.message_handler(func=lambda m: m.text == "🗑 Удалить карту")
def admin_delete_list(m):
    username = m.from_user.username or ""
    if username.lower() in [a.lower() for a in ADMINS]:
        cards = load_db('cards')
        if not cards:
            return bot.send_message(m.chat.id, "База пуста.")
        
        markup = types.InlineKeyboardMarkup()
        for c in cards:
            markup.add(types.InlineKeyboardButton(text=f"❌ {c['name']}", callback_data=f"delcard_{c['name']}"))
        
        bot.send_message(m.chat.id, "Нажми на карту, чтобы удалить её из базы:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("delcard_"))
def handle_delete_card(call):
    name = call.data.split("_")[1]
    cards = load_db('cards')
    
    new_cards = [c for c in cards if c['name'] != name]
    save_db(new_cards, 'cards')
    
    bot.edit_message_text(f"✅ Карта {name} удалена из системы.", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def back_to_main(m):
    bot.send_message(m.chat.id, "Возвращаемся в меню...", reply_markup=main_kb(m.from_user))

@bot.message_handler(func=lambda m: m.text == "💎 Премиум")
def show_premium(m):
    bot.send_message(
        m.chat.id, 
        "💎 **Премиум статус**\n\n• Получение карт без КД\n• Уникальная роль в топе\n\n✉️ По вопросам покупки: @verybigsun", 
        parse_mode="Markdown"
    )

# --- [7] ЗАПУСК ---

if __name__ == '__main__':
    print("Бот запущен. Ожидание сообщений...")
    bot.infinity_polling()
