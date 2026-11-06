import os
import threading
import requests
from flask import Flask
from telebot import TeleBot

# ফ্লাস্ক অ্যাপ তৈরি করা (রেন্ডারের পোর্ট রিকোয়ারমেন্ট পূরণের জন্য)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# টেলিগ্রাম বট সেটআপ
TOKEN = "8859026903:AAGIx3xypVJ_XASWBSjxWDjmYkdVE_SO5U4"
bot = TeleBot(TOKEN)

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

PRIVATE_CHANNEL_ID = -1004460747665  # তোমার প্রাইভেট চ্যানেলের আইডি

@bot.message_handler(commands=['start'])
def handle_start(message):
    text_parts = message.text.split()
    
    if len(text_parts) > 1:
        movie_id = text_parts[1]
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        # ডেটাবেজ থেকে telegram_parts কলাম ফেচ করা
        supabase_query_url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}&select=telegram_parts"
        
        try:
            response = requests.get(supabase_query_url, headers=headers)
            data = response.json()
            
            if data and len(data) > 0 and data[0].get('telegram_parts'):
                channel_message_id = int(data[0]['telegram_parts'])
                
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

@bot.message_handler(commands=['save'])
def handle_save(message):
    print("Received /save command!")  # লগে দেখার জন্য যাতে বোঝা যায় কমান্ড হিট হয়েছে
    if message.reply_to_message:
        text_parts = message.text.split()
        if len(text_parts) > 1:
            movie_id = text_parts[1]
            forwarded_msg_id = message.reply_to_message.message_id
            
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            
            # সুপাবেজের telegram_parts কলামে মেসেজ আইডি আপডেট করার URL
            supabase_update_url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}"
            payload = {
                "telegram_parts": str(forwarded_msg_id)
            }
            
            try:
                # ডেটাবেজে রিকোয়েস্ট পাঠানো
                response = requests.patch(supabase_update_url, json=payload, headers=headers)
                print(f"Supabase Response Status: {response.status_code}")
                
                if response.status_code in [200, 204]:
                    bot.reply_to(message, f"✅ Success! Movie ID: {movie_id} matched with Telegram Message ID: {forwarded_msg_id} and saved to database.")
                else:
                    bot.reply_to(message, f"⚠️ Failed to update database. Status code: {response.status_code}")
                    
            except Exception as e:
                print(f"Error saving to db: {e}")
                bot.reply_to(message, "⚠️ An error occurred while saving to database!")
                
        else:
            bot.reply_to(message, "⚠️ Please provide the Movie ID after /save command (e.g., /save 23)")
    else:
        bot.reply_to(message, "⚠️ Please reply to the movie file/post with /save <movie_id>")

if __name__ == '__main__':
    # ফ্লাস্ক সার্ভার আলাদা ব্যাকগ্রাউন্ড থ্রেডে চালু করা
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Bot is starting polling...")
    try:
        bot.remove_webhook()
    except Exception as e:
        print(f"Webhook remove error: {e}")
        
    bot.infinity_polling(skip_pending=True)
