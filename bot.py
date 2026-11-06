import os
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app_web = Flask('')

@app_web.route('/')
def home():
    return "Piracy Vault Bot is Alive and Running!"

def run_flask():
    app_web.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args 
    if args and args[0] == "spider_man":
        await update.message.reply_text("Fetching your movie files, please wait a moment...")
        
        chat_id = "@vault96_bot"
        file_message_ids = [101, 102, 103, 104, 105]
        
        for msg_id in file_message_ids:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=chat_id,
                message_id=msg_id
            )
    else:
        await update.message.reply_text("Welcome to Piracy Vault! Please click the correct movie link from our website to access your content.")

if __name__ == '__main__':
    keep_alive()
    TOKEN = os.environ.get("BOT_TOKEN")
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()
