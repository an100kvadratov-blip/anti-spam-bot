import os
import re
import logging
import threading
import time
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv


# === HEALTH CHECK СЕРВЕР ДЛЯ KOYEB === #
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, format, *args):
        # Отключаем логирование health check запросов
        return


def run_health_server():
    """Запуск health check сервера в отдельном потоке"""
    try:
        server = HTTPServer(('0.0.0.0', 8000), HealthHandler)
        print("🌐 Health server запущен на 0.0.0.0:8000")
        server.timeout = 1  # Таймаут для частой проверки выхода
        while True:
            server.handle_request()
            time.sleep(1)
    except Exception as e:
        print(f"❌ Ошибка health server: {e}")


# Запускаем health server только в веб-среде
if os.environ.get('KOYEB') or os.environ.get('WEB_ENV'):
    try:
        health_thread = threading.Thread(target=run_health_server, daemon=True)
        health_thread.start()
        print("✅ Health server запущен в фоновом режиме")
    except Exception as e:
        print(f"❌ Не удалось запустить health server: {e}")

# === КОНЕЦ HEALTH CHECK СЕРВЕРА === #

# Загрузка переменных из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable is not set!")
    raise ValueError("BOT_TOKEN environment variable is not set!")

# ID владельца
OWNER_IDS = [1263482853]

# ID канала, сообщения от которого не нужно удалять
CHANNEL_ID = -1002207248459

# Чёрный список слов и паттернов для фильтрации спама
SPAM_PATTERNS = [
    r"https?://", r"www\.", r"\.(com|ru|org|net|info|bot|me)/?", r"t\.me/", r"@[a-zA-Z0-9_]{5,}",
    r"подработк", r"заработок", r"заработать", r"ваканси", r"работ[аыу]", r"работать",
    r"пиши\s*(в?\s*(лс|личку|личные|пм|pm|dm))", r"обращайся", r"напиши", r"свяжись",
    r"инвест", r"бизнес", r"партнер", r"франшиз", r"крипт", r"биткоин",
    r"быстры[ей]? деньги", r"легк[аои]? заработок", r"на дому", r"удаленн", r"удалённ",
    r"набор.*(сотрудник|персонал|работник)", r"требуются", r"требуется",
    r"\+?\d{10,}", r"@\w{5,}", r"контакт", r"телефон", r"whatsapp", r"вайбер",
    r"бесплатно", r"бонус", r"акци", r"скидк", r"выгодн", r"предложен",
    r"млм", r"сетевой", r"маркетинг", r"8000", r"8\s*000", r"8к", r"8\s*[кk]",
    r"деньги", r"выплат", r"получаешь", r"за\s*4\s*час", r"несколько\s*дней",
    r"нужны\s+люди", r"требуются", r"ищем", r"для\s+работы", r"удаленн",
    r"подработк", r"без\s+вложений", r"без\s+опыта", r"в\s+свободное\s+время"
]

# Время в течение которого пользователь считается новым (24 часа)
NEW_USER_TIME = timedelta(hours=24)

# Хранилище времени вступления пользователей
user_join_times = {}


class AntiSpamBot:
    def __init__(self):
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in SPAM_PATTERNS]

    def is_spam(self, text: str) -> bool:
        """Проверяет текст на наличие спам-паттернов"""
        if not text:
            return False

        text_lower = text.lower()
        spam_keywords = ["http", "www", ".com", ".ru", ".org", "@", "t.me", "подработ", "заработ", "+ лс", "пиши",
                         "набор"]

        if any(keyword in text_lower for keyword in spam_keywords):
            return True

        for pattern in self.compiled_patterns:
            if pattern.search(text):
                return True

        return False

    def is_new_user(self, chat_id: int, user_id: int) -> bool:
        """Проверяет, является ли пользователь новым"""
        join_time = user_join_times.get((chat_id, user_id))
        if not join_time:
            return False
        return datetime.now() - join_time < NEW_USER_TIME

    async def track_user_join(self, chat_id: int, user_id: int):
        """Записывает время вступления пользователя"""
        user_join_times[(chat_id, user_id)] = datetime.now()
        logger.info(f"User {user_id} joined chat {chat_id}")

    async def is_admin_or_owner(self, message, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Проверяет, является ли пользователь администратором или владельцем"""
        try:
            user_id = message.from_user.id

            if user_id in OWNER_IDS:
                logger.info(f"👑 Сообщение от владельца: {message.from_user.first_name}")
                return True

            chat_member = await context.bot.get_chat_member(message.chat.id, user_id)
            if chat_member.status in ['creator', 'administrator']:
                logger.info(f"👑 Сообщение от администратора: {message.from_user.first_name}")
                return True

        except Exception as e:
            logger.error(f"Ошибка проверки прав: {e}")
        return False


# Создаем экземпляр бота
antispam_bot = AntiSpamBot()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        await update.message.reply_text(
            "🚫 Антиспам-бот активирован!\n\n"
            "Добавьте меня в группу как администратора с правами:\n"
            "• Удаление сообщений\n• Блокировка пользователей\n\n"
            "Я буду автоматически удалять спам!"
        )
        logger.info("Start command received")
    except Exception as e:
        logger.error(f"Error in start command: {e}")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает ID пользователя"""
    try:
        user_id = update.message.from_user.id
        await update.message.reply_text(f"🆔 Ваш ID: `{user_id}`", parse_mode='Markdown')
        logger.info(f"User {user_id} requested their ID")
    except Exception as e:
        logger.error(f"Error in myid command: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех сообщений"""
    try:
        message = update.message
        if not message or not message.from_user:
            return

        chat_id = message.chat_id
        user_id = message.from_user.id
        text = message.text or message.caption or ""

        # Пропускаем сообщения от ботов
        if message.from_user.is_bot:
            return

        # Пропускаем пересланные сообщения из канала
        if message.forward_from_chat and message.forward_from_chat.id == CHANNEL_ID:
            logger.info(f"📢 Пропущено пересланное сообщение из канала {CHANNEL_ID}")
            return

        # Пропускаем сообщения от самого канала
        if user_id == CHANNEL_ID:
            logger.info(f"📢 Пропущено прямое сообщение от канала {CHANNEL_ID}")
            return

        # Пропускаем сообщения от администраторов и владельца
        if await antispam_bot.is_admin_or_owner(message, context):
            logger.info(f"⚠️ Пропущено сообщение от администратора/владельца: {user_id}")
            return

        # Проверяем на спам
        if antispam_bot.is_spam(text):
            try:
                await message.delete()
                logger.info(f"Deleted spam message from user {user_id} in chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to delete message: {e}")

    except Exception as e:
        logger.error(f"Error in handle_message: {e}")


async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик новых участников"""
    try:
        chat_id = update.message.chat_id
        for member in update.message.new_chat_members:
            if not member.is_bot:
                await antispam_bot.track_user_join(chat_id, member.id)
        logger.info(f"New members joined chat {chat_id}")
    except Exception as e:
        logger.error(f"Error in handle_new_members: {e}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}")


def main():
    """Основная функция запуска бота"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("myid", myid))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.CAPTION, handle_message))
        application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
        application.add_error_handler(error_handler)

        logger.info("Бот запускается...")
        print("🤖 Антиспам-бот запущен!")
        print("📍 Токен:", BOT_TOKEN[:10] + "..." if BOT_TOKEN else "Not set")
        print("👑 ID владельца:", OWNER_IDS)
        print("📢 Разрешенный канал:", CHANNEL_ID)

        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    main()