import telebot, pymongo, random, os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# CONFIG (Environment Variables ကို သုံးပါ)
bot = telebot.TeleBot(os.getenv("TOKEN"))
db = pymongo.MongoClient(os.getenv("MONGO_URI"))['bot_database']
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS").split(",")]

# Memory Cache (မြန်ဆန်စေရန်)
brain_cache = {}
for doc in db['brain'].find():
    inp = doc['input_text']
    if inp not in brain_cache: brain_cache[inp] = []
    brain_cache[inp].append({"reply": doc.get("reply_text"), "sticker": doc.get("sticker_id")})

# /start Command
@bot.message_handler(commands=['start'])
def start_msg(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Add Me To Your Group", url=f"https://t.me/{bot.get_me().username}?startgroup=true"))
    text = (
        "🤖 မင်္ဂလာပါ! ကျွန်တော်က သင်တို့ရဲ့ Group တွေကို အသက်ဝင်စေမယ့် Myanmar Friend Bot ပါ။\n\n"
        "💬 လုပ်ဆောင်ချက်များ:\n"
        "• သင်ပြောသမျှကို သင်ယူပြီး စကားပြန်ပြောပေးခြင်း။\n"
        "• Sticker တွေကိုလည်း မှတ်သားပြီး ပြန်လည်အသုံးပြုခြင်း။\n\n"
        "အောက်က Button ကိုနှိပ်ပြီး သင့် Group ထဲကို ခေါ်ဆောင်လိုက်ပါ။ 🚀"
    )
    bot.send_message(m.chat.id, text, reply_markup=kb)

# /broadcast Command
@bot.message_handler(commands=['broadcast'])
def broadcast(m):
    if m.from_user.id in ADMIN_IDS and m.reply_to_message:
        groups = db['settings_collection'].find_one({"_id": "bot_config"}).get("groups", [])
        for gid in groups:
            try: bot.forward_message(gid, m.chat.id, m.reply_to_message.message_id)
            except: continue
        bot.reply_to(m, "✅ Broadcast ပို့ပြီးပါပြီ။")

# Learning & Reply System
@bot.message_handler(func=lambda m: True)
def handle(m):
    # Learn (Reply ထောက်ထားရင်)
    if m.reply_to_message:
        inp = m.reply_to_message.text.lower().strip()
        reply, stk = m.text, (m.sticker.file_id if m.sticker else None)
        # အဖြေတူနေရင် မမှတ်တော့ဘူး
        if inp in brain_cache and any(i['reply'] == reply and i['sticker'] == stk for i in brain_cache[inp]): return
        
        db['brain'].insert_one({"input_text": inp, "reply_text": reply, "sticker_id": stk})
        if inp not in brain_cache: brain_cache[inp] = []
        brain_cache[inp].append({"reply": reply, "sticker": stk})
        return

    # Reply (စာသားအတိုင်းပြန်ဖြေ)
    text = m.text.lower().strip() if m.text else ""
    if text in brain_cache:
        choice = random.choice(brain_cache[text])
        if choice['sticker']: bot.send_sticker(m.chat.id, choice['sticker'], reply_to_message_id=m.message_id)
        elif choice['reply']: bot.reply_to(m, choice['reply'])
    
    # Auto Register Group (Database ထဲ group ID မှတ်ထားပေး)
    if m.chat.type in ['group', 'supergroup']:
        db['settings_collection'].update_one({"_id": "bot_config"}, {"$addToSet": {"groups": m.chat.id}}, upsert=True)

if __name__ == '__main__':
    bot.infinity_polling(skip_pending=True)
