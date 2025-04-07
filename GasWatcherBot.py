from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import asyncio
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

# Словарь для хранения порогов по chat_id
thresholds = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я слежу за газом в сети Ethereum. Напиши /gas чтобы узнать текущую цену газа 🚦")

async def gas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gas_info = get_gas_info()
    if gas_info:
        safe, propose, fast = gas_info
        message = (
            f"💨 Текущая цена газа в Gwei:\n"
            f"• 🟢 Медленно: {safe} Gwei\n"
            f"• 🟡 Средне: {propose} Gwei\n"
            f"• 🔴 Быстро: {fast} Gwei"
        )
    else:
        message = "Не удалось получить данные о газе 😓"

    await update.message.reply_text(message)

async def set_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        value = int(context.args[0])
        thresholds[chat_id] = value
        print(f"[INFO] Установлен порог {value} Gwei для чата {chat_id}")
        await update.message.reply_text(f"Буду следить за газом и дам знать, когда опустится до {value} Gwei 🚦")
    except (IndexError, ValueError):
        await update.message.reply_text("Пожалуйста, укажи число: /set <число>")

async def cancel_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in thresholds:
        del thresholds[chat_id]
        print(f"[INFO] Отменено отслеживание для чата {chat_id}")
        await update.message.reply_text("Окей, больше не слежу за газом ❌")
    else:
        await update.message.reply_text("Ты ещё не устанавливал порог для отслеживания")

def get_gas_info():
    try:
        url = f"https://api.etherscan.io/api?module=gastracker&action=gasoracle&apikey={ETHERSCAN_API_KEY}"
        response = requests.get(url).json()
        result = response["result"]
        return int(result["SafeGasPrice"]), int(result["ProposeGasPrice"]), int(result["FastGasPrice"])
    except Exception as e:
        print(f"[ERROR] Не удалось получить цену газа: {e}")
        return None

async def monitor_gas(app):
    while True:
        gas_info = get_gas_info()
        if gas_info:
            _, propose, _ = gas_info
            for chat_id, threshold in list(thresholds.items()):
                if propose <= threshold:
                    print(f"[INFO] Gwei ({propose}) <= порог ({threshold}) — отправка уведомления в чат {chat_id}")
                    await app.bot.send_message(chat_id=chat_id, text=f"🚨 Цена газа достигла {propose} Gwei! Это ниже заданного порога {threshold} Gwei.")
                    del thresholds[chat_id]
        await asyncio.sleep(60)  # Проверка каждую минуту

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gas", gas))
    app.add_handler(CommandHandler("set", set_threshold))
    app.add_handler(CommandHandler("cancel", cancel_threshold))

    app.job_queue.run_once(lambda *_: asyncio.create_task(monitor_gas(app)), 0)

    print("[INFO] Бот запущен")
    app.run_polling()
