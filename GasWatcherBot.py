import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

# Храним пороги пользователей
user_thresholds = {}

# Фоновый планировщик
scheduler = BackgroundScheduler()
scheduler.start()

# Получение текущего газа
def get_gas_price():
    url = f"https://api.etherscan.io/api?module=gastracker&action=gasoracle&apikey={ETHERSCAN_API_KEY}"
    try:
        response = requests.get(url, timeout=10).json()
        return int(response["result"]["ProposeGasPrice"])
    except:
        return None

# Проверка порогов пользователей
async def check_gas_thresholds(application):
    gas_price = get_gas_price()
    if gas_price is None:
        return

    for user_id, threshold in list(user_thresholds.items()):
        if gas_price <= threshold:
            try:
                await application.bot.send_message(
                    chat_id=user_id,
                    text=f"🚨 Газ упал до {gas_price} Gwei — это ниже или равно твоему порогу ({threshold} Gwei)!"
                )
            except Exception as e:
                print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")

            # Удаляем, чтобы не слал постоянно
            user_thresholds.pop(user_id)

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши /set <число> чтобы установить порог цены газа для уведомления.\nНапиши /cancel чтобы отменить отслеживание.")

async def gas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gas_price = get_gas_price()
    if gas_price is not None:
        await update.message.reply_text(f"💨 Текущая цена газа: {gas_price} Gwei")
    else:
        await update.message.reply_text("Не удалось получить цену газа 😓")

async def set_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        threshold = int(context.args[0])
        user_thresholds[update.effective_user.id] = threshold
        await update.message.reply_text(f"✅ Порог установлен: {threshold} Gwei. Я отправлю уведомление, когда газ опустится ниже или до этого уровня.")
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Пожалуйста, укажи порог как целое число. Пример: /set 20")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_thresholds.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ Отслеживание порога отключено.")

# Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gas", gas))
    app.add_handler(CommandHandler("set", set_threshold))
    app.add_handler(CommandHandler("cancel", cancel))

    # Планировщик будет проверять каждые 60 сек
    scheduler.add_job(lambda: app.create_task(check_gas_thresholds(app)), "interval", seconds=60)

    app.run_polling()
