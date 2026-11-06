import os
import requests
from flask import Flask, request
import telebot

TOKEN = os.environ.get('BOT_TOKEN')  # Tomar bot token environment variable theke nibe
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# Supabase Credentials (Tomar database-er details ekhane thakbe)
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# Private Channel ID (Tomar channel-er ID, jevabe age 4460747665 chilo, tar age '-100' add korte hoy)
PRIVATE_CHANNEL_ID = -1004460747665 

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_str = request.stream.read().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

@bot.message_handler(commands=['start'])
def handle_start(message):
    text_parts = message.text.split()
    
    if len(text_parts) > 1:
        file_slug = text_parts[1]  # Ekhane english name ba slug ta pabe (jemon: spider_man)
        
        # Supabase theke oi english name diye query kore channel er post number ba message_id khuje ber korbo
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        # Supabase table-er nam 'movies' ba tomar table er nam onujai query korbe
        supabase_query_url = f"{SUPABASE_URL}/rest/v1/movies?slug=eq.{file_slug}&select=message_id"
        
        try:
            response = requests.get(supabase_query_url, headers=headers)
            data = response.json()
            
            if data and len(data) > 0:
                channel_message_id = int(data[0]['message_id'])
                
                # Sotti karer private channel theke file ta userer kase copy kore pathiye dibe
                bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=PRIVATE_CHANNEL_ID,
                    message_id=channel_message_id
                )
            else:
                bot.reply_to(message, "Sorry, the file was not found in the database!")
                
        except Exception as e:
            bot.reply_to(message, "An error occurred while fetching your file!")
            
    else:
        # Jodi keu emnei bot e start dey
        bot.reply_to(message, "👋 Welcome to Piracy Vault! Please browse our official website and click the 'Telegram' button on any movie or series to access your content.")

@app.route('/')
def index():
    return "Bot is running smoothly!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
