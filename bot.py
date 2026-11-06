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

# --- Render-এর ফ্রি টিয়ারের পোর্ট বাইন্ডিং ঠিক রাখার জন্য ফ্লাস্ক সার্ভার ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is active and running smoothly!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
# ------------------------------------------------------------------------

# Supabase Credentials (Fetch from environment variables)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

async def fetch_movie_from_supabase(movie_id: str):
    """Fetches movie details from Supabase using the given movie ID."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase credentials are missing in environment variables!")
        return None

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}&select=*"
    
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
    args = context.args  # Captures deep link argument (e.g., movie_[id])
    
    if args:
        param = args[0]
        if param.startswith("movie_"):
            movie_id = param.split("_")[1]
            logger.info(f"User {user.id} (Username: {user.username}) requested movie ID: {movie_id}")
            
            # Send searching status message
            status_message = await update.message.reply_text(
                f"🎬 Request received for Movie ID: `{movie_id}`.\n"
                f"🔍 Searching our vault for your file. Please wait...",
                parse_mode="Markdown"
            )
            
            # Fetch movie record from Supabase
            movie = await fetch_movie_from_supabase(movie_id)
            
            if not movie:
                await status_message.edit_text(
                    f"⚠️ **Oops! Movie Not Found**\n\n"
                    f"We couldn't find any file matching ID: `{movie_id}` in our vault.\n"
                    f"It might have been removed or the link is outdated. Please check back on the website.",
                    parse_mode="Markdown"
                )
                return
            
            # Extract details safely
            title = movie.get("title", "Unknown Title")
            year = movie.get("year", "")
            
            # Extract download link directly or from 'downloads' JSON array
            file_link = movie.get("link") or movie.get("magnet") or movie.get("url")
            
            if not file_link and "downloads" in movie and isinstance(movie["downloads"], list) and len(movie["downloads"]) > 0:
                first_dl = movie["downloads"][0]
                file_link = first_dl.get("link") or first_dl.get("url") or first_dl.get("magnet")
            
            if not file_link:
                file_link = "No direct link available"
            
            # Final success message
            await status_message.edit_text(
                f"✅ **File Found Successfully!**\n\n"
                f"🎬 **Title:** {title} ({year})\n\n"
                f"📥 **Download Link:**\n{file_link}\n\n"
                f"Enjoy your media! Powered by **Piracy Vault**.",
                parse_mode="Markdown"
            )
            return

    # Default /start message
    await update.message.reply_text(
        f"👋 Welcome to **Piracy Vault**, {user.first_name}!\n\n"
        f"Please browse our official website and click the **'Get on Telegram'** button on any movie card to securely access your content.",
        parse_mode="Markdown"
    )

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    
    if not TOKEN:
        logger.error("BOT_TOKEN environment variable is missing!")
        return

    # ব্যাকগ্রাউন্ডে ফ্লাস্ক সার্ভার রান করা যাতে রেন্ডার পোর্ট পেয়ে যায়
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    logger.info("Bot is starting up with Flask Health Check...")
    application.run_polling()

if __name__ == "__main__":
    main()
