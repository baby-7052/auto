import telebot, pymongo, random, os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# CONFIGURATION
bot = telebot.TeleBot(os.getenv("TOKEN"))
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client['bot_database']
brain_collection = db['brain']
settings_collection = db['settings_collection']
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS").split(",")]

# Cache အတွက် Memory ထဲမှာ အရင်ဆွဲတင်ထားမယ်
brain_cache = {}
def load_cache():
    global brain_cache
    brain_cache = {}
    for doc in brain_collection.find():
        inp = doc['input_text']
        if inp not in brain_cache: brain_cache[inp] = []
        brain_cache[inp].append({"reply": doc.get("reply_text"), "sticker": doc.get("sticker_id")})
    print(f"✅ Cache Loaded: {len(brain_cache)} entries.")

load_cache()

# START COMMAND
@bot.message_handler(commands=['start'])
def start_msg(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Add Me To Your Group", url=f"https://t.me/{bot.get_me().username}?startgroup=true"))
    text = (
        "🤖 မင်္ဂလာပါ! ကျွန်တော်က သင်တို့ရဲ့ Group တွေကို အသက်ဝင်စေမယ့် Myanmar Friend Bot ပါ။\n\n"
        "💬 လုပ်ဆောင်ချက်များ:\n"
        "• စကားပြော/Sticker များကို သင်ယူပြီး ပြန်လည်ဖြေကြားပေးခြင်း။\n\n"
        "အောက်က Button ကိုနှိပ်ပြီး သင့် Group ထဲကို ခေါ်ဆောင်လိုက်ပါ။ 🚀"
    )
    bot.send_message(m.chat.id, text, reply_markup=kb)

# BROADCAST COMMAND
@bot.message_handler(commands=['broadcast'])
def broadcast(m):
    if m.from_user.id in ADMIN_IDS and m.reply_to_message:
        config = settings_collection.find_one({"_id": "bot_config"})
        groups = config.get("groups", []) if config else []
        for gid in groups:
            try: bot.forward_message(gid, m.chat.id, m.reply_to_message.message_id)
            except: continue
        bot.reply_to(m, "✅ Broadcast ပို့ပြီးပါပြီ။")

# MAIN HANDLING (Learn & Reply)
@bot.message_handler(func=lambda m: True)
def handle(m):
    # 1. LEARNING SYSTEM (Reply ထောက်ထားရင် မှတ်မယ်)
    if m.reply_to_message:
        # Input ကို စာဖြစ်ဖြစ် Sticker ID ဖြစ်ဖြစ် ယူမယ်
        parent = m.reply_to_message.text.lower().strip() if m.reply_to_message.text else (m.reply_to_message.sticker.file_id if m.reply_to_message.sticker else None)
        
        if parent:
            reply_text = m.text
            reply_stk = m.sticker.file_id if m.sticker else None
            
            # တူညီတာရှိမရှိ စစ်မယ်
            if parent in brain_cache and any(i['reply'] == reply_text and i['sticker'] == reply_stk for i in brain_cache[parent]): 
                return
            
            # DB ထဲ မှတ်မယ်
            brain_collection.insert_one({"input_text": parent, "reply_text": reply_text, "sticker_id": reply_stk})
            if parent not in brain_cache: brain_cache[parent] = []
            brain_cache[parent].append({"reply": reply_text, "sticker": reply_stk})
            return

    # 2. FAST REPLY SYSTEM
    current_input = m.text.lower().strip() if m.text else (m.sticker.file_id if m.sticker else None)
    
    if current_input and current_input in brain_cache:
        choice = random.choice(brain_cache[current_input])
        if choice['sticker']: 
            bot.send_sticker(m.chat.id, choice['sticker'], reply_to_message_id=m.message_id)
        if choice['reply']: 
            bot.reply_to(m, choice['reply'])
    
    # 3. AUTO REGISTER GROUP
    if m.chat.type in ['group', 'supergroup']:
        settings_collection.update_one({"_id": "bot_config"}, {"$addToSet": {"groups": m.chat.id}}, upsert=True)

if __name__ == '__main__':
    print("🚀 Bot is running...")
    bot.infinity_polling(skip_pending=True)
