import os
import threading
import requests
from flask import Flask
from telebot import TeleBot

# ফ্লাস্ক অ্যাপ তৈরি করা (রেন্ডারের পোর্ট রিকোয়েস্ট পূরণের জন্য)
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

# ইউজারের শেষ ফরোয়ার্ড করা মেসেজ আইডি মনে রাখার জন্য ডিকশনারি
user_last_forwarded = {}

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

# ফরোয়ার্ড করা ফাইল ট্র্যাক করার হ্যান্ডলার
@bot.message_handler(content_types=['document', 'video', 'audio', 'photo'])
def handle_forwarded_files(message):
    if message.forward_from_chat or message.forward_from:
        user_last_forwarded[message.chat.id] = message.message_id
        bot.reply_to(message, "📥 File received! Now reply or send `/save <movie_id>` to link this file.")

@bot.message_handler(commands=['save'])
def handle_save(message):
    print("Received /save command!")
    text_parts = message.text.split()
    
    if len(text_parts) > 1:
        movie_id = text_parts[1]
        
        # প্রথমে চেক করি মেসেজটি সরাসরি ক্যাপশনসহ ফরোয়ার্ড করা হয়েছে কি না
        forwarded_msg_id = getattr(message, 'forward_from_message_id', None)
        
        # যদি ক্যাপশন ছাড়া আলাদা ফরোয়ার্ড করা হয়, তবে মেমোরি থেকে আইডি নিই
        if not forwarded_msg_id and message.chat.id in user_last_forwarded:
            forwarded_msg_id = user_last_forwarded[message.chat.id]
            
        if not forwarded_msg_id:
            bot.reply_to(message, "⚠️ Please forward a file from your channel first, then send /save <movie_id>")
            return
            
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"  # সুপাবেজ যেন আপডেট হওয়া ডেটা রিটার্ন করে
        }
        
        # সুপাবেজের telegram_parts কলামে মেসেজ আইডি আপডেট করার URL
        supabase_update_url = f"{SUPABASE_URL}/rest/v1/movies_vault?id=eq.{movie_id}"
        payload = {
            "telegram_parts": str(forwarded_msg_id)
        }
        
        try:
            response = requests.patch(supabase_update_url, json=payload, headers=headers)
            print(f"Supabase Status: {response.status_code}")
            print(f"Supabase Response: {response.text}")
            
            if response.status_code in [200, 204]:
                res_data = response.json() if response.text else []
                if res_data:
                    bot.reply_to(message, f"✅ Success! Movie ID: {movie_id} matched with Telegram Message ID: {forwarded_msg_id} and saved to database.")
                else:
                    bot.reply_to(message, f"⚠️ Supabase returned success, but no rows were updated. Check if ID {movie_id} exists or check RLS policies!")
                
                # সেভ হয়ে গেলে ডিকশনারি থেকে ক্লিয়ার করে দিই
                if message.chat.id in user_last_forwarded:
                    del user_last_forwarded[message.chat.id]
            else:
                bot.reply_to(message, f"⚠️ Failed to update database. Status: {response.status_code}, Msg: {response.text}")
                
        except Exception as e:
            print(f"Error saving to db: {e}")
            bot.reply_to(message, "⚠️ An error occurred while saving to database!")
            
    else:
        bot.reply_to(message, "⚠️ Please provide the Movie ID after /save command (e.g., /save 23)")

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
