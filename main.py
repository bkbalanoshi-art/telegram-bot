import asyncio
import os
import json
import static_ffmpeg
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, idle
from pyrogram.errors import (
    FloodWait, PhoneCodeExpired, PhoneCodeInvalid, SessionPasswordNeeded, PeerIdInvalid
)

# تنظیمات اصلی
static_ffmpeg.add_paths()
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
SESSIONS_FILE = "sessions.json"

active_clients = {}
pending_logins = {} # {chat_id: {"phone": ..., "hash": ..., "client": ...}}
IRAN_TZ = ZoneInfo("Asia/Tehran")
DEFAULT_NAME = "𝗞𝗛𝗔𝗡"
TIME_NAME_ACTIVE = False

# --- توابع مدیریت فایل ---
def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_session(uid, ss):
    data = load_sessions()
    data[str(uid)] = ss
    with open(SESSIONS_FILE, "w") as f: json.dump(data, f)

# --- کلاینت اصلی ---
app = Client(
    "khan_master",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

# --- تابع کمکی برای ادیت امن پیام ---
async def safe_edit(message, text):
    try:
        await message.edit_text(text)
    except Exception:
        pass

# --- هندلر دستورات ---
@app.on_message(filters.me)
async def handle_everything(client, message):
    global TIME_NAME_ACTIVE
    if not message.text: return
    
    cmd = message.text.lower()
    chat_id = message.chat.id

    # 1. تست سلامت
    if cmd == "پینگ":
        await safe_edit(message, "🚀 **سلف‌بات آنلاین است!**")

    # 2. آمار
    elif cmd == "آمار":
        count = len(active_clients) + 1
        await safe_edit(message, f"📊 تعداد اکانت‌های فعال: `{count}`")

    # 3. ساعت
    elif cmd == "ساعت":
        now = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
        await safe_edit(message, f"🇮🇷 ساعت ایران: `{now}`")

    # 4. شروع لاگین (ریپلای روی شماره)
    elif message.reply_to_message and cmd == "لاگین":
        phone = message.reply_to_message.text.strip()
        await safe_edit(message, f"⏳ ارسال کد برای `{phone}`...")
        
        tmp_client = Client(":memory:", api_id=API_ID, api_hash=API_HASH)
        try:
            await tmp_client.connect()
            code_data = await tmp_client.send_code(phone)
            pending_logins[chat_id] = {
                "phone": phone,
                "hash": code_data.phone_code_hash,
                "client": tmp_client
            }
            await safe_edit(message, "✅ کد ارسال شد.\nحالا روی کد ۵ رقمی ریپلای کنید و بفرستید: `تایید`")
        except Exception as e:
            await safe_edit(message, f"❌ خطا: {str(e)}")

    # 5. تایید لاگین (ریپلای روی کد)
    elif message.reply_to_message and cmd == "تایید":
        login_info = pending_logins.get(chat_id)
        if not login_info:
            await safe_edit(message, "❌ ابتدا باید `لاگین` بزنید.")
            return
            
        code = message.reply_to_message.text.strip()
        await safe_edit(message, "⏳ در حال ورود...")
        
        try:
            tmp = login_info["client"]
            await tmp.sign_in(login_info["phone"], login_info["hash"], code)
            session = await tmp.export_session_string()
            me = await tmp.get_me()
            
            # ذخیره سشن
            save_session(me.id, session)
            
            # استارت کلاینت جدید
            new_client = Client(f"sub_{me.id}", API_ID, API_HASH, session_string=session)
            await new_client.start()
            active_clients[str(me.id)] = new_client
            
            await safe_edit(message, f"🎉 سلف‌بات روی اکانت `{me.first_name}` فعال شد!")
            del pending_logins[chat_id]
        except Exception as e:
            await safe_edit(message, f"❌ خطا: {str(e)}")

    # 6. اسم ساعتی
    elif cmd == "تایم فعال":
        TIME_NAME_ACTIVE = True
        await safe_edit(message, "✅ اسم ساعتی روشن شد.")
    
    elif cmd == "تایم خاموش":
        TIME_NAME_ACTIVE = False
        await safe_edit(message, "❌ اسم ساعتی خاموش شد.")

# --- تسک ساعت در پس‌زمینه ---
async def time_bg():
    while True:
        if TIME_NAME_ACTIVE:
            try:
                now = datetime.now(IRAN_TZ).strftime("%H:%M")
                bold = "".join(["𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗:"[int(c) if c!=':' else 10] for c in now])
                await app.update_profile(first_name=f"{DEFAULT_NAME} ┃ {bold}")
            except Exception: pass
        await asyncio.sleep(60)

# --- استارت‌آپ اصلی ---
async def start_all():
    print("--- در حال روشن کردن سلف‌بات اصلی ---")
    await app.start()
    
    # لود سشن‌های ذخیره شده
    saved = load_sessions()
    for uid, ss in saved.items():
        try:
            c = Client(f"sub_{uid}", API_ID, API_HASH, session_string=ss)
            await c.start()
            active_clients[uid] = c
            print(f"Account {uid} is Online.")
        except Exception:
            print(f"Account {uid} Failed.")

    asyncio.create_task(time_bg())
    print("--- پلتفرم آماده استفاده است ---")
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_all())
