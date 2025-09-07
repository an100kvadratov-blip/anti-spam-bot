import re
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Ваш API-токен от @BotFather
import os
TOKEN = os.getenv("TOKEN", "YOUR_BOT_TOKEN_HERE")  # Берет токен из переменной окружения или запасной

# Чёрный список слов для фильтрации спама
SPAM_KEYWORDS = ["http", "www.", ".com", ".ru", ".org", "@", "t.me", "подработку", "заработок", "+ ЛС", "Нужна подработка", "Пиши +"]

# Время в секундах, в течение которого пользователь считается новым (24 часа)
NEW_USER_TIME = 24 * 60 * 60

# Хранилище времени вступления пользователей в чат
user_join_times = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Антиспам-бот запущен! Добавьте меня в чат как администратора.")

async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.from_user:
        return

    chat_id = message.chat_id
    user_id = message.from_user.id
    current_time = time.time()

    # Проверка, является ли пользователь новым
    join_time = user_join_times.get((chat_id, user_id))
    is_new_user = join_time and (current_time - join_time < NEW_USER_TIME)

    # Проверка на спам (ссылки или ключевые слова)
    text = message.text or message.caption or ""
    is_spam = any(keyword.lower() in text.lower() for keyword in SPAM_KEYWORDS) or bool(
        re.search(r"(https?://|www\.|\.com|\.ru|\.org|t\.me/|@)", text, re.IGNORECASE)
    )

    if is_new_user and is_spam:
        try:
            await message.delete()
            await message.chat.send_message(
                f"Сообщение от {message.from_user.username or message.from_user.first_name} удалено как спам."
            )
            # Опционально: бан пользователя
            # await context.bot.ban_chat_member(chat_id, user_id)
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Регистрация времени вступления новых участников
    for member in update.message.new_chat_members:
        user_join_times[(update.message.chat_id, member.id)] = time.time()

def main():
    app = Application.builder().token(TOKEN).build()

    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()