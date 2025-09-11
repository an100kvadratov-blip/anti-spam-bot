import os
import re
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import os
import re
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# === HEALTH CHECK СЕРВЕР ДЛЯ KOYEB === #
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

def run_health_server():
    server = HTTPServer(('0.0.0.0', 8000), HealthHandler)
    print("🌐 Health server запущен на 0.0.0.0:8000")
    server.serve_forever()

# Запускаем только в веб-среде
if os.environ.get('KOYEB') or os.environ.get('WEB_ENV'):
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
# === КОНЕЦ HEALTH CHECK СЕРВЕРА === #

# Загрузка переменных из .env файла
load_dotenv()
# Замена для imghdr в Python 3.13+
import mimetypes

# Загружаем переменные из .env файла
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

# ID владельца (замените на ваш реальный ID)
OWNER_IDS = [1263482853]  # ⚠️ ЗАМЕНИТЕ НА ВАШ REAL ID!

# ⭐⭐ ID канала, сообщения от которого не нужно удалять ⭐⭐
CHANNEL_ID = -1002207248459


# Чёрный список слов и паттернов для фильтрации спама
SPAM_PATTERNS = [
    # Ссылки и домены
    r"https?://",
    r"www\.",
    r"\.(com|ru|org|net|info|bot|me|xyz|shop|online)/?",
    r"t\.me/",
    r"@[a-zA-Z0-9_]{5,}",

    # Работа и заработок
    r"подработк",
    r"заработок",
    r"заработать",
    r"ваканси",
    r"работ[аыу]",
    r"работать",
    r"зарплата",
    r"доход",
    r"карьер",

    # Призывы к действию
    r"пиши\s*(в?\s*(лс|личку|личные|пм|pm|dm))",
    r"обращайся",
    r"обратитесь",
    r"напиши",
    r"напишите",
    r"свяжись",
    r"свяжитесь",
    r"звони",
    r"звоните",
    r"звонок",

    # Финансовые схемы
    r"инвест",
    r"бизнес",
    r"партнер",
    r"франшиз",
    r"крипт",
    r"биткоин",
    r"bitcoin",
    r"блокчейн",

    # Быстрый заработок
    r"быстры[ей]? деньги",
    r"легк[аои]? заработок",
    r"на дому",
    r"удаленн",
    r"удалённ",
    r"онлайн",

    # Набор сотрудников
    r"набор.*(сотрудник|персонал|работник)",
    r"требуются",
    r"требуется",
    r"ищем.*(сотрудник|работник)",

    # Контакты
    r"\+?\d{10,}",  # телефоны
    r"@\w{5,}",  # упоминания
    r"контакт",
    r"телефон",
    r"whatsapp",
    r"вайбер",
    r"viber",
    r"telegram",

    # Подозрительные предложения
    r"бесплатно",
    r"бонус",
    r"акци",
    r"скидк",
    r"выгодн",
    r"предложен",

    # Сетевой маркетинг
    r"млм",
    r"сетевой",
    r"маркетинг",

    # Деньги и суммы
    r"8000",
    r"8\s*000",  # 8 000
    r"8,000",
    r"8к",
    r"8\s*[кk]",
    r"8\s*тыс",
    r"на\s+руки",  # "на руки"
    r"заработок",
    r"заработок",  # с опечаткой
    r"деньги",
    r"выплат",
    r"получаешь",

    # Время и простота
    r"за\s*4\s*час",  # за 4 час(а)
    r"за\s*четыре\s*час",
    r"несколько\s*дней",
    r"на\s+несколько\s+дней",
    r"простой",
    r"простая",
    r"проще\s+простого",
    r"легк",
    r"быстр",
    r"за\s*день",

    # Поиск людей
    r"нужны\s+люди",
    r"требуются",
    r"ищем",
    r"для\s+работы",
    r"удаленн",  # удаленно, удаленная
    r"удаленк",

    # Прочее
    r"подработк",
    r"без\s+вложений",
    r"без\s+опыта",
    r"в\s+свободное\s+время",
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

        # Быстрая проверка по ключевым словам
        spam_keywords = ["http", "www", ".com", ".ru", ".org", "@", "t.me", "подработ", "заработ", "+ лс", "пиши",
                         "набор"]
        if any(keyword in text_lower for keyword in spam_keywords):
            return True

        # Глубокая проверка по regex паттернам
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

    async def is_admin_or_owner(self, message: Update.message, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Проверяет, является ли пользователь администратором или владельцем"""
        try:
            chat_id = message.chat.id
            user_id = message.from_user.id

            # Проверяем по ID владельца
            if user_id in OWNER_IDS:
                logger.info(f"👑 Сообщение от владельца: {message.from_user.first_name}")
                return True

            # Проверяем права администратора в чате
            chat_member = await context.bot.get_chat_member(chat_id, user_id)

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
            "• Удаление сообщений\n"
            "• Блокировка пользователей\n\n"
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

        # ⭐⭐ НОВОЕ: Пропускаем пересланные сообщения из КОНКРЕТНОГО КАНАЛА ⭐⭐
        CHANNEL_ID = -1002207248459  # ID вашего канала
        if (message.forward_from_chat and
            message.forward_from_chat.id == CHANNEL_ID):
            logger.info(f"📢 Пропущено пересланное сообщение из канала {CHANNEL_ID}")
            return

        # ⭐⭐ ИЛИ: Пропускаем сообщения от самого канала (если он пишет напрямую) ⭐⭐
        if user_id == CHANNEL_ID:
            logger.info(f"📢 Пропущено прямое сообщение от канала {CHANNEL_ID}")
            return

        # Пропускаем сообщения от администраторов и владельца
        if await antispam_bot.is_admin_or_owner(message, context):
            logger.info(f"⚠️ Пропущено сообщение от администратора/владельца: {user_id}")
            return

        # ДЛЯ ОТЛАДКИ
        print(f"Получено сообщение: '{text}'")
        print(f"Спам? {antispam_bot.is_spam(text)}")

        # ПРОВЕРЯЕМ НА СПАМ
        if antispam_bot.is_spam(text):
            print("Удаляем спам!")  # ДЛЯ ОТЛАДКИ
            try:
                # Удаляем сообщение
                await message.delete()
                logger.info(f"Deleted spam message from user {user_id} in chat {chat_id}")

            except Exception as e:
                print(f"Ошибка удаления: {e}")  # ДЛЯ ОТЛАДКИ
                logger.error(f"Failed to delete message: {e}")

    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        raise


if __name__ == "__main__":
    main()