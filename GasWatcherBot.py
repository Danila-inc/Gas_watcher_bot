import os
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, JobQueue, Job
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

# Словарь для хранения порогов по chat_id
thresholds = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напиши /set <число> чтобы установить порог для уведомления о газе ⛽️\n"
        "Команда /cancel отменяет отслеживание."
    )

async def gas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gas_price = await get_gas_price()
    if gas_price is None:
        await update.message.reply_text("Не удалось получить данные о газе 😓")
        return
    safe, propose, fast = gas_price
    await update.message.reply_text(
        f"💨 Текущая цена газа в Gwei:\n"
        f"• 🟢 Медленно: {safe}\n"
        f"• 🟡 Средне: {propose}\n"
        f"• 🔴 Быстро: {fast}"
    )

async def set_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Укажи целое число, например: /set 5")
        return
    threshold = int(context.args[0])
    thresholds[chat_id] = threshold
    await update.message.reply_text(f"Буду слать пуш, когда газ станет ≤ {threshold} Gwei")

    job_queue: JobQueue = context.job_queue
    job_name = f"monitor_{chat_id}"

    # Сначала удалим старую задачу, если есть
    old_job = job_queue.get_jobs_by_name(job_name)
    for job in old_job:
        job.schedule_removal()

    # Запускаем новую задачу
    job_queue.run_repeating(callback=check_gas_and_notify, interval=60, first=0, name=job_name, data=chat_id)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    job_name = f"monitor_{chat_id}"
    jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in jobs:
        job.schedule_removal()
    if chat_id in thresholds:
        del thresholds[chat_id]
    await update.message.reply_text("Окей, отменил отслеживание газа!")

async def check_gas_and_notify(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    if chat_id not in thresholds:
        return
    threshold = thresholds[chat_id]
    gas_price = await get_gas_price()
    if gas_price is None:
        return
    safe, _, _ = gas_price
    if int(safe) <= threshold:
        await context.bot.send_message(chat_id, f"🚨 Газ сейчас {safe} Gwei, что ≤ порога {threshold}!")

async def get_gas_price():
    try:
        url = f"https://api.etherscan.io/api?module=gastracker&action=gasoracle&apikey={ETHERSCAN_API_KEY}"
        response = requests.get(url).json()
        result = response['result']
        return int(result['SafeGasPrice']), int(result['ProposeGasPrice']), int(result['FastGasPrice'])
    except:
        return None

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gas", gas))
    app.add_handler(CommandHandler("set", set_threshold))
    app.add_handler(CommandHandler("cancel", cancel))

    # Убедимся, что переменная без пробелов и с https
    external_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        webhook_url=f"{external_url}/{TOKEN}",
        url_path=TOKEN,
    )

