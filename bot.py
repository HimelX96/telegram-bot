import os
import logging
import httpx
from flask import Flask
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Render-er port binding o 24/7 active rakhari jonno Flask server ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is active and running smoothly!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
# ------------------------------------------------------------------------

# Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

async def fetch_movie_from_supabase(movie_name: str):
    """Supabase rest API scale query using title."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase credentials are missing in environment variables!")
        return None

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    url = f"{SUPABASE_URL}/rest/v1/movies_vault?title=ilike.*{movie_name}*&select=*"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0]
    except Exception as e:
        logger.error(f"Error connecting to Supabase: {e}")
        
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args  # Captures deep link argument
    
    if args:
        param = args[0]
        if param.startswith("movie_"):
            clean_param = param.replace("movie_", "")
            
            target_season = None
            target_episode = None
            series_name = clean_param
            
            # Series/K-Drama check: e.g. movie_kingdom_s1_e4 or movie_kingdom_s2_e1
            if "_s" in clean_param and "_e" in clean_param:
                try:
                    parts = clean_param.split("_s")
                    series_name = parts[0].replace("_", " ").strip()
                    se_parts = parts[1].split("_e")
                    target_season = se_parts[0].strip()
                    target_episode = se_parts[1].strip()
                except Exception as e:
                    logger.error(f"Error parsing season/episode: {e}")
            else:
                # Normal movie check: e.g. movie_3_idiots
                series_name = clean_param.replace("_", " ").strip()
            
            logger.info(f"User {user.id} requested: Name: '{series_name}', Season: {target_season}, Episode: {target_episode}")
            
            # Search status message
            status_text = f"🎬 **Request received:** `{series_name}`"
            if target_season and target_episode:
                status_text += f" (Season {target_season}, Episode {target_episode})"
            
            status_message = await update.message.reply_text(
                f"{status_text}\n🔍 Searching vault. Please wait...",
                parse_mode="Markdown"
            )
            
            # Fetch from Supabase
            movie = await fetch_movie_from_supabase(series_name)
            
            if not movie:
                await status_message.edit_text(
                    f"⚠️ **Oops! Item Not Found**\n\n"
                    f"We couldn't find any title matching `{series_name}` in our vault.",
                    parse_mode="Markdown"
                )
                return
            
            title = movie.get("title", "Unknown Title")
            year = movie.get("year", "")
            
            file_link = None
            episode_info_text = ""
            
            # 1. TV Series / K-Drama Handling (season & episode match)
            if target_episode and "episode_download" in movie and isinstance(movie["episode_download"], list):
                for ep in movie["episode_download"]:
                    ep_num = str(ep.get("episode_number", ""))
                    ep_season = str(ep.get("season_number", target_season or "1"))
                    
                    # Match both episode number (and season if specified)
                    if ep_num == str(target_episode):
                        dl_link = ep.get("download_link") or ep.get("link") or ep.get("telegram_link") or ep.get("url")
                        if dl_link and not dl_link.startswith("magnet:?"):
                            file_link = dl_link
                            ep_quality = ep.get("quality", "1080p")
                            ep_size = ep.get("size", "")
                            
                            season_str = f"S{target_season}" if target_season else f"S{ep_season}"
                            episode_info_text = f"\n📺 **Season & Episode:** {season_str}E{ep_num} | **Quality:** {ep_quality}"
                            if ep_size:
                                episode_info_text += f" | **Size:** {ep_size}"
                            episode_info_text += "\n"
                            break
            
            # 2. Movie Handling (Direct links)
            if not file_link:
                candidate_links = [
                    movie.get("telegram_link"),
                    movie.get("tg_link"),
                    movie.get("stream_link"),
                    movie.get("link"),
                    movie.get("url")
                ]
                for cl in candidate_links:
                    if cl and not cl.startswith("magnet:?"):
                        file_link = cl
                        break
            
            # 3. Downloads array fallback (if no direct link found)
            if not file_link and "downloads" in movie and isinstance(movie["downloads"], list):
                for dl in movie["downloads"]:
                    dl_link = dl.get("link") or dl.get("url") or dl.get("telegram")
                    if dl_link and not dl_link.startswith("magnet:?"):
                        file_link = dl_link
                        break
            
            if not file_link:
                file_link = "No direct Telegram file link available."
            
            # Final output message
            await status_message.edit_text(
                f"✅ **File Found Successfully!**\n\n"
                f"🎬 **Title:** {title} ({year})"
                f"{episode_info_text}\n"
                f"📥 **Download Link:**\n{file_link}\n\n"
                f"Enjoy your media! Powered by **Piracy Vault**.",
                parse_mode="Markdown"
            )
            return

    # Default /start message
    await update.message.reply_text(
        f"👋 Welcome to **Piracy Vault**, {user.first_name}!\n\n"
        f"Please browse our official website and click the **'Get on Telegram'** button on any movie or series to access your content.",
        parse_mode="Markdown"
    )

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    
    if not TOKEN:
        logger.error("BOT_TOKEN environment variable is missing!")
        return

    # Flask background thread
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    logger.info("Bot is starting with Movie & Series/K-Drama link support...")
    application.run_polling()

if __name__ == "__main__":
    main()
