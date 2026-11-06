import os
import requests
from flask import Flask, request
import telebot

# সরাসরি কোডের ভেতরে টোকেন বসিয়ে দেওয়া হলো যাতে কোনো ভুল না হয়
TOKEN = "9129296107:AAHJJa4xE23HXnDySCoLss5mebK_z3CVRJO"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

PRIVATE_CHANNEL_ID = -1004460747665  # তোমার প্রাইভেট চ্যানেলের আইডি

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_str = request.stream.read().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

# /start কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def handle_start(message):
    text_parts = message.text.split()
    
    if len(text_parts) > 1:
        movie_id = text_parts[1]
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        supabase_query_url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}&select=message_id"
        
        try:
            response = requests.get(supabase_query_url, headers=headers)
            data = response.json()
            
            if data and len(data) > 0:
                channel_message_id = int(data[0]['message_id'])
                
                bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=PRIVATE_CHANNEL_ID,
                    message_id=channel_message_id
                )
            else:
                bot.reply_to(message, f"❌ Sorry! File not found in database for ID: {movie_id}")
                
        except Exception as e:
            bot.reply_to(message, "⚠️ An error occurred while fetching your file!")
            
    else:
        bot.reply_to(message, "👋 Welcome to Piracy Vault!\n\nPlease browse our official website and click the 'Telegram' button on any movie or series to access your content.")

# /save কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['save'])
def handle_save(message):
    if message.reply_to_message:
        text_parts = message.text.split()
        if len(text_parts) > 1:
            movie_id = text_parts[1]
            forwarded_msg_id = message.reply_to_message.message_id
            
            bot.reply_to(message, f"✅ Received! Movie ID: {movie_id}, Message ID: {forwarded_msg_id}\n(Now update this in your Supabase table)")
        else:
            bot.reply_to(message, "⚠️ Please provide the Movie ID after /save command (e.g., /save 116)")
    else:
      bot.reply_to(message, "⚠️ Please reply to the movie file/post with /save <movie_id>")

@app.route('/')
def index():
    return "Piracy Vault Bot is running smoothly!"

# অটো ওয়েবহুক সেট করার রুট
@app.route('/set_webhook')
def set_webhook():
    webhook_url = f"https://telegram-bot-6mrg.onrender.com/{TOKEN}"
    api_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
    response = requests.get(api_url)
    return response.json()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
