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

# 1. File cache kora
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
        await message.reply_text(f"Cached! Total queued: {file_count}. Now send `/saveseason <id> <season_no> <start_ep>`")

# 2. Season-wise episode save korar command
async def save_season_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id not in latest_file_cache or not latest_file_cache[chat_id]:
        await update.message.reply_text("Kono file cache kora nei! Prothome episode gulo forward karo.")
        return

    if len(context.args) < 3:
        await update.message.reply_text("Sothik niyome command dao! Udahoron: `/saveseason <movie_id> <season_no> <start_ep>`\nJemon: `/saveseason 55 1 1`", parse_mode="Markdown")
        return

    movie_id = context.args[0]
    target_season = int(context.args[1])
    start_ep = int(context.args[2])
    
    file_ids = latest_file_cache[chat_id]

    # Database theke purono JSON data anha
    get_url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}&select=episode_download"
    
    async with httpx.AsyncClient() as client:
        res = await client.get(get_url, headers=SUPABASE_HEADERS)
        
        seasons_list = []
        if res.status_code == 200 and res.json():
            row = res.json()[0]
            seasons_list = row.get("episode_download") or []
            if not isinstance(seasons_list, list):
                seasons_list = []

        # 3. Target season khuje ber kora ba na thakle notun toiri kora
        season_obj = None
        for s in seasons_list:
            if s.get("season_number") == target_season:
                season_obj = s
                break
        
        if not season_obj:
            season_obj = {
                "season_number": target_season,
                "episodes": []
            }
            seasons_list.append(season_obj)

        # 4. Episode gulo season-er `episodes` array-te serial-wise add kora
        existing_episodes = season_obj.get("episodes", [])
        
        for index, f_id in enumerate(file_ids):
            current_ep_num = start_ep + index
            
            # Jodi oi episode number age thekei thake, update kore dibo
            ep_found = False
            for ep in existing_episodes:
                if ep.get("episode_number") == current_ep_num:
                    ep["telegram_file_id"] = f_id
                    ep_found = True
                    break
            
            if not ep_found:
                existing_episodes.append({
                    "episode_number": current_ep_num,
                    "telegram_file_id": f_id,
                    "title": f"Season {target_season} Episode {current_ep_num}",
                    "quality": "1080p REMUX"
                })
        
        season_obj["episodes"] = existing_episodes

        # 5. Supabase-e update (PATCH) kora
        patch_url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}"
        payload = {"episode_download": seasons_list}
        
        update_res = await client.patch(patch_url, json=payload, headers=SUPABASE_HEADERS)

        if update_res.status_code in [200, 204]:
            latest_file_cache[chat_id] = []
            await update.message.reply_text(f"Success! ID {movie_id}-er Season {target_season}-er episode gulo safolkhae save hoyeche.")
        else:
            update_text = getattr(update_res, 'text', str(update_res))
            await update.message.reply_text(f"Failed to update database: {update_text}")

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, handle_message))
    application.add_handler(CommandHandler("saveseason", save_season_command))

    application.run_polling()

if __name__ == '__main__':
    main()
