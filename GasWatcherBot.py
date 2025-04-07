import os
import requests
import asyncio
from telegram import Update, Bot
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
        if not ETHERSCAN_API_KEY:
            print("❌ Ошибка: переменная ETHERSCAN_API_KEY не установлена!")
            return None

        url = f"https://api.etherscan.io/api?module=gastracker&action=gasoracle&apikey={ETHERSCAN_API_KEY}"
        response = requests.get(url)
        print(f"🌐 Ответ от Etherscan: {response.status_code}, {response.text}")
        data = response.json()

        if data.get("status") != "1":
            print(f"❌ Некорректный ответ от Etherscan: {data}")
            return None

        result = data['result']
        return int(result['SafeGasPrice']), int(result['ProposeGasPrice']), int(result['FastGasPrice'])
    except Exception as e:
        print(f"❌ Ошибка при получении цены газа: {e}")
        return None

if __name__ == "__main__":
    async def unset_webhook():
        bot = Bot(token=TOKEN)
        await bot.delete_webhook(drop_pending_updates=True)
        print("🔧 Вебхук удалён (если был)")

    asyncio.run(unset_webhook())

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gas", gas))
    app.add_handler(CommandHandler("set", set_threshold))
    app.add_handler(CommandHandler("cancel", cancel))
    print("🚀 Бот запущен в режиме polling...")
    app.run_polling()
