import os
import re
import requests
from flask import Flask, request
import telebot

TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
PRIVATE_CHANNEL_ID = int(os.environ.get("PRIVATE_CHANNEL_ID", "-1004460747665"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)


def supabase_headers():
    return {
apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def parse_movie_id(payload: str):
    """
    Accepts: movie_116 | 116 | id_116
    Returns int or None
    """
    if not payload:
        return None
    payload = payload.strip()
    m = re.search(r"(\d+)", payload)
    return int(m.group(1)) if m else None


def parse_parts(raw):
    """
    telegram_parts examples:
      101,102,103
      101, 102, 103
    Returns sorted unique-ish list preserving given order after numeric sort by part order as stored.
    Store already in serial order in DB: 101,102,103
    """
    if not raw:
        return []
    parts = []
    for bit in str(raw).split(","):
        bit = bit.strip()
        if bit.isdigit():
            parts.append(int(bit))
    return parts


def fetch_telegram_parts(movie_id: int):
    url = (
        f"{SUPABASE_URL}/rest/v1/movies_vault"
        f"?id=eq.{movie_id}&select=id,title,telegram_parts"
    )
    r = requests.get(url, headers=supabase_headers(), timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None, []
    row = data[0]
    return row.get("title") or f"ID {movie_id}", parse_parts(row.get("telegram_parts"))


@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.stream.read().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


@bot.message_handler(commands=["start"])
def handle_start(message):
    text_parts = (message.text or "").split(maxsplit=1)

    # Plain /start
    if len(text_parts) == 1:
        bot.reply_to(
            message,
            "👋 Welcome to Piracy Vault!\n"
            "Open the website and tap the Telegram button on a title.",
        )
        return

    payload = text_parts[1].strip()
    movie_id = parse_movie_id(payload)
    if not movie_id:
        bot.reply_to(message, "Invalid link. Use the Telegram button from the website.")
        return

    try:
        title, parts = fetch_telegram_parts(movie_id)
        if title is None:
            bot.reply_to(message, "Sorry, this title was not found in the database.")
            return
        if not parts:
            bot.reply_to(
                message,
                f"“{title}” has no Telegram files linked yet.\n"
                f"(telegram_parts is empty for id {movie_id})",
            )
            return

        # Header
        if len(parts) == 1:
            bot.send_message(message.chat.id, f"🎬 {title}\n📦 1 file")
        else:
            bot.send_message(
                message.chat.id,
                f"🎬 {title}\n📦 {len(parts)} parts — sending in order 1→{len(parts)}",
            )

        # Send in serial order (as stored in telegram_parts)
        for idx, msg_id in enumerate(parts, start=1):
            try:
                bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=PRIVATE_CHANNEL_ID,
                    message_id=msg_id,
                )
            except Exception:
                bot.send_message(
                    message.chat.id,
                    f"⚠️ Could not send part {idx} (channel message_id {msg_id}).",
                )

        if len(parts) > 1:
            bot.send_message(message.chat.id, "✅ All parts sent. Join/extract in order.")

    except Exception:
        bot.reply_to(message, "An error occurred while fetching your file.")


@app.route("/")
def index():
    return "Bot is running smoothly!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
