from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging
import os

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Bot activo en la Raspberry!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Mensaje recibido: {update.message.text}")
    await update.message.reply_text(f"Recibido: {update.message.text}")

if __name__ == '__main__':
    logging.info("Iniciando bot...")
    try:
        application = Application.builder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
        logging.info("Entrando en run_polling()...")
        application.run_polling()
    except Exception as e:
        logging.exception(f"Error al iniciar el bot: {e}")