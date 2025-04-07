from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import os

# Вставь свой токен сюда
BOT_TOKEN = "7812855786:AAFx5Vc4qELbUJcBHBVkjy1tcaeB_gvSk2s"

# Etherscan API (можно позже зарегистрировать ключ)
ETHERSCAN_API_KEY = "DBURNPNEDHGJNZUCMUARRHIWZSA7656U3R"  # общедоступный тестовый

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