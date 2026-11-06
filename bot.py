import os
from flask import Flask, request
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

app = Flask(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Ekhane Service Role Key use korbe

# Temporary memory to store recent file/album IDs per chat
latest_file_cache = {}

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message = update.message
    
    file_id = None
    media_group_id = message.media_group_id

    # Check file type (Document, Video, Audio etc.)
    if message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.audio:
        file_id = message.audio.file_id

    if file_id:
        if chat_id not in latest_file_cache:
            latest_file_cache[chat_id] = []
        
        # Jodi album ba ekadhik file ashe, list-e add hote thakbe
        if file_id not in latest_file_cache[chat_id]:
            latest_file_cache[chat_id].append(file_id)
        
        file_count = len(latest_file_cache[chat_id])
        await message.reply_text(f"File cached! Total queued: {file_count}. Now send `/save <movie_id>` to store them sequentially.")

async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id not in latest_file_cache or not latest_file_cache[chat_id]:
        await update.message.reply_text("Kono file cache kora nei! Prothome file ba album forward karo.")
        return

    if not context.args:
        await update.message.reply_text("Sothik niyome command dao! Uddahoron: `/save 23`", parse_mode="Markdown")
        return

    movie_id = context.args[0]
    new_file_ids = latest_file_cache[chat_id]

    # 1. Prothome database theke check korbo age ki data ache
    get_url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}&select=telegram_parts"
    
    async with httpx.AsyncClient() as client:
        res = await client.get(get_url, headers=SUPABASE_HEADERS)
        
        existing_parts = ""
        if res.status_code == 200 and res.json():
            row = res.json()[0]
            existing_parts = row.get("telegram_parts") or ""

        # 2. Purono parts er sathe notun file ID gulo comma diye serial-wise jure dibo
        new_parts_str = ",".join(new_file_ids)
        
        if existing_parts:
            # Jodi age thekei kisu thake, tar sathe comma diye notun gulo append hobe
            updated_parts = f"{existing_parts},{new_parts_str}"
        else:
            updated_parts = new_parts_str

        # 3. Supabase-e PATCH (Update) request pathabo
        patch_url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}"
        payload = {"telegram_parts": updated_parts}
        
        update_res = await client.patch(patch_url, json=payload, headers=SUPABASE_HEADERS)

        if update_res.status_code in [200, 204]:
            # Cache clear kore dibo save howar por
            latest_file_cache[chat_id] = []
            await update.message.reply_text(f"Success! Movie ID {movie_id}-e serial parts successfully save/update hoyeche: `{updated_parts}`", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Failed to update database: {update_res.text}")

# Telegram bot initialization setup (python-telegram-bot v20+)
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, handle_message))
    application.add_handler(CommandHandler("save", save_command))

    application.run_polling()

if __name__ == '__main__':
    main()
