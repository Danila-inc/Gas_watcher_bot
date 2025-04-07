import os
import logging
from threading import Thread
from aiohttp import web
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    JobQueue,
)

# --- Настройка логгирования ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
user_thresholds = {}

# --- Health Check для Render ---
async def health_check(request):
    return web.Response(text="Gas Bot is OK")

def run_health_check():
    app = web.Application()
    app.router.add_get("/", health_check)
    web.run_app(app, port=8080, host='0.0.0.0')

# --- Команды бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔔 Бот мониторинга газа Ethereum\n"
        "Команды:\n"
        "/gas - текущая цена\n"
        "/set <число> - установить порог (например: 25.5)\n"
        "/cancel - отменить уведомления"
    )

async def gas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gas_price = await get_gas_price()
    if not gas_price:
        await update.message.reply_text("⚠️ Ошибка получения данных")
        return
    
    safe, propose, fast = gas_price
    await update.message.reply_text(
        f"⛽️ Текущий газ (Gwei):\n"
        f"• 🟢 Safe: {safe:.1f}\n"
        f"• 🟡 Propose: {propose:.1f}\n"
        f"• 🔴 Fast: {fast:.1f}"
    )

async def set_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    try:
        threshold = round(float(context.args[0]), 2)
        if threshold <= 0:
            await update.message.reply_text("❌ Порог должен быть > 0!")
            return
            
        # Проверка дубля
        if chat_id in user_thresholds and user_thresholds[chat_id] == threshold:
            await update.message.reply_text(f"ℹ️ Порог уже {threshold:.2f} Gwei")
            return
            
    except (IndexError, ValueError, TypeError):
        await update.message.reply_text("ℹ️ Формат: /set <число> (например: 5.7)")
        return

    gas_price = await get_gas_price()
    if not gas_price:
        await update.message.reply_text("⚠️ Ошибка получения данных")
        return

    safe_gas = gas_price[0]
    user_thresholds[chat_id] = threshold

    if safe_gas <= threshold:
        await update.message.reply_text(f"🚨 Уже {safe_gas:.2f} ≤ {threshold:.2f} Gwei!")
        return

    if 'job' in context.chat_data:
        context.chat_data['job'].schedule_removal()

    job = context.job_queue.run_repeating(
        check_gas,
        interval=60.0,
        first=10.0,
        chat_id=chat_id,
        data={'threshold': threshold}
    )
    context.chat_data['job'] = job

    await update.message.reply_text(
        f"✅ Установлен порог: {threshold:.2f} Gwei\n"
        f"Текущий: {safe_gas:.2f} Gwei\n"
        f"Уведомлю при снижении до ≤ {threshold:.2f}!"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id in user_thresholds:
        del user_thresholds[chat_id]
    
    if 'job' in context.chat_data:
        context.chat_data['job'].schedule_removal()
        del context.chat_data['job']
    
    await update.message.reply_text("🔕 Уведомления отключены!")

async def check_gas(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    threshold = job.data['threshold']
    
    gas_price = await get_gas_price()
    if not gas_price:
        return

    safe_gas = gas_price[0]
    
    if safe_gas <= threshold:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🚨 Газ {safe_gas:.2f} ≤ {threshold:.2f} Gwei!"
        )
        job.schedule_removal()
        if chat_id in user_thresholds:
            del user_thresholds[chat_id]

# --- Получение цены газа ---
async def get_gas_price():
    try:
        url = f"https://api.etherscan.io/api?module=gastracker&action=gasoracle&apikey={ETHERSCAN_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get("status") != "1":
            raise ValueError("API error")
            
        return (
            float(data['result']['SafeGasPrice']),
            float(data['result']['ProposeGasPrice']),
            float(data['result']['FastGasPrice'])
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return None

# --- Запуск ---
def main():
    # Health Check в отдельном потоке
    health_thread = Thread(target=run_health_check)
    health_thread.daemon = True
    health_thread.start()

    # Инициализация бота
    application = ApplicationBuilder() \
        .token(TOKEN) \
        .job_queue(JobQueue()) \
        .build()

    # Регистрация обработчиков
    handlers = [
        CommandHandler("start", start),
        CommandHandler("gas", gas),
        CommandHandler("set", set_threshold),
        CommandHandler("cancel", cancel)
    ]
    for handler in handlers:
        application.add_handler(handler)

    logger.info("Бот запущен на Render!")
    application.run_polling(
        poll_interval=5,
        timeout=30,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()