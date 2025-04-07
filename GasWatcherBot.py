from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import os


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я слежу за газом в сети Ethereum. Напиши /gas чтобы узнать текущую цену газа 🚦")

async def gas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = f"https://api.etherscan.io/api?module=gastracker&action=gasoracle&apikey={ETHERSCAN_API_KEY}"
    response = requests.get(url).json()

    try:
        safe = response['result']['SafeGasPrice']
        propose = response['result']['ProposeGasPrice']
        fast = response['result']['FastGasPrice']
        message = (
            f"💨 Текущая цена газа в Gwei:\n"
            f"• 🟢 Медленно: {safe} Gwei\n"
            f"• 🟡 Средне: {propose} Gwei\n"
            f"• 🔴 Быстро: {fast} Gwei"
        )
    except Exception:
        message = "Не удалось получить данные о газе 😓"

    await update.message.reply_text(message)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gas", gas))
    app.run_polling()