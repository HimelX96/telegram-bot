import os
from flask import Flask
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Service Role Key

latest_file_cache = {}

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ১. ফাইল বা জিপ ক্যাশ করা
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message = update.message
    
    file_id = None
    if message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.audio:
        file_id = message.audio.file_id

    if file_id:
        if chat_id not in latest_file_cache:
            latest_file_cache[chat_id] = []
        
        if file_id not in latest_file_cache[chat_id]:
            latest_file_cache[chat_id].append(file_id)
        
        file_count = len(latest_file_cache[chat_id])
        await message.reply_text(f"File cached! Total queued: {file_count}. Now send command: `/save <movie_id> <quality>`\nExample: `/save 62 remux`")

# ২. কোয়ালিটি অনুযায়ী সেভ করার কমান্ড
async def save_quality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id not in latest_file_cache or not latest_file_cache[chat_id]:
        await update.message.reply_text("কোনো ফাইল ক্যাশ করা নেই! প্রথমে ফাইল বা জিপ ফরোয়ার্ড করো।")
        return

    if len(context.args) < 2:
        await update.message.reply_text("সঠিক নিয়মে কমান্ড দাও! উদাহরণ: `/save <movie_id> <quality>`\nযেমন: `/save 62 remux` বা `/save 62 webdl`", parse_mode="Markdown")
        return

    movie_id = context.args[0]
    quality_name = context.args[1].upper()  # REMUX বা WEB-DL
    
    file_ids = latest_file_cache[chat_id]
    # যদি একাধিক পার্ট বা জিপ থাকে লিস্ট থাকবে, ১টা থাকলে সিঙ্গেল স্ট্রিং
    file_payload = file_ids[0] if len(file_ids) == 1 else file_ids

    # ডাটাবেজ থেকে আগের ডাটা আনা
    get_url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}&select=episode_download"
    
    async with httpx.AsyncClient() as client:
        res = await client.get(get_url, headers=SUPABASE_HEADERS)
        
        qualities_list = []
        if res.status_code == 200 and res.json():
            row = res.json()[0]
            qualities_list = row.get("episode_download") or []
            if not isinstance(qualities_list, list):
                qualities_list = []

        # কোয়ালিটি অলরেডি আছে কি না চেক করে আপডেট বা নতুন যোগ করা
        q_found = False
        for item in qualities_list:
            if item.get("quality") == quality_name:
                item["telegram_file_id"] = file_payload
                q_found = True
                break
        
        if not q_found:
            qualities_list.append({
                "quality": quality_name,
                "telegram_file_id": file_payload
            })

        # সুপাবেজে PATCH (Update) করা
        patch_url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}"
        payload = {"episode_download": qualities_list}
        
        update_res = await client.patch(patch_url, json=payload, headers=SUPABASE_HEADERS)

        if update_res.status_code in [200, 204]:
            latest_file_cache[chat_id] = []
            await update.message.reply_text(f"Success! ID {movie_id}-এর [{quality_name}] কোয়ালিটি সফলভাবে সেভ হয়েছে।")
        else:
            update_text = getattr(update_res, 'text', str(update_res))
            await update.message.reply_text(f"Failed to update database: {update_text}")

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, handle_message))
    application.add_handler(CommandHandler("save", save_quality_command))

    application.run_polling()

if __name__ == '__main__':
    main()
