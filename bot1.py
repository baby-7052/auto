import telebot, pymongo, random, os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# CONFIGURATION
bot = telebot.TeleBot(os.getenv("TOKEN"))
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client['bot_database']
brain_collection = db['brain']
settings_collection = db['settings_collection']
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS").split(",")]

# Cache အတွက် Memory
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
    # Private chat ဖြစ်ရင် user ID မှတ်မယ်
    if m.chat.type == 'private':
        settings_collection.update_one({"_id": "bot_config"}, {"$addToSet": {"users": m.chat.id}}, upsert=True)
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Add Me To Your Group", url=f"https://t.me/{bot.get_me().username}?startgroup=true"))
    text = "🤖 မင်္ဂလာပါ! စကားပြောbot ဖြစ်ပါသည် အောက်က Button နှိပ်ပြီး Group ထဲ ခေါ်ဆောင်လိုက်ပါ။ 🚀"
    bot.send_message(m.chat.id, text, reply_markup=kb)

# BROADCAST COMMAND (Users & Groups အကုန်ပို့မယ်)
@bot.message_handler(commands=['broadcast'])
def broadcast(m):
    if m.from_user.id in ADMIN_IDS and m.reply_to_message:
        config = settings_collection.find_one({"_id": "bot_config"}) or {}
        # Group ID တွေရော User ID တွေရော စုမယ်
        targets = list(set(config.get("groups", []) + config.get("users", [])))
        
        success = 0
        for tid in targets:
            try:
                bot.forward_message(tid, m.chat.id, m.reply_to_message.message_id)
                success += 1
            except: continue
        bot.reply_to(m, f"✅ Broadcast အောင်မြင်စွာ ပို့ပြီးပါပြီ။ (နေရာပေါင်း {success} ခုသို့)")

# MAIN HANDLING
@bot.message_handler(func=lambda m: True)
def handle(m):
    # 1. LEARNING SYSTEM
    if m.reply_to_message:
        parent = m.reply_to_message.text.lower().strip() if m.reply_to_message.text else (m.reply_to_message.sticker.file_id if m.reply_to_message.sticker else None)
        if parent:
            reply_text, reply_stk = m.text, (m.sticker.file_id if m.sticker else None)
            if parent in brain_cache and any(i['reply'] == reply_text and i['sticker'] == reply_stk for i in brain_cache[parent]): return
            brain_collection.insert_one({"input_text": parent, "reply_text": reply_text, "sticker_id": reply_stk})
            if parent not in brain_cache: brain_cache[parent] = []
            brain_cache[parent].append({"reply": reply_text, "sticker": reply_stk})
            return

    # 2. FAST REPLY
    current_input = m.text.lower().strip() if m.text else (m.sticker.file_id if m.sticker else None)
    if current_input and current_input in brain_cache:
        choice = random.choice(brain_cache[current_input])
        if choice['sticker']: bot.send_sticker(m.chat.id, choice['sticker'], reply_to_message_id=m.message_id)
        if choice['reply']: bot.reply_to(m, choice['reply'])
    
    # 3. AUTO REGISTER (Groups & Users)
    if m.chat.type in ['group', 'supergroup']:
        settings_collection.update_one({"_id": "bot_config"}, {"$addToSet": {"groups": m.chat.id}}, upsert=True)
    elif m.chat.type == 'private':
        settings_collection.update_one({"_id": "bot_config"}, {"$addToSet": {"users": m.chat.id}}, upsert=True)

if __name__ == '__main__':
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
