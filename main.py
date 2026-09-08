import asyncio
import os
import json
import re
import static_ffmpeg
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, idle
from pyrogram.errors import (
    FloodWait, PhoneCodeExpired, PhoneCodeInvalid, SessionPasswordNeeded, PeerIdInvalid
)

# تنظیمات
static_ffmpeg.add_paths()
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
SESSIONS_FILE = "sessions.json"

active_clients = {}
pending_logins = {}
IRAN_TZ = ZoneInfo("Asia/Tehran")
DEFAULT_NAME = "𝗞𝗛𝗔𝗡"
TIME_NAME_ACTIVE = False

# --- مدیریت سشن‌ها ---
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

# --- تابع کمکی برای حل مشکل Peer ID و ادیت پیام ---
async def safe_edit(client, message, text):
    try:
        # اجبار کلاینت به شناسایی چت
        await client.get_chat(message.chat.id)
        await message.edit_text(text)
    except Exception:
        # اگر ادیت نشد، یک پیام جدید می‌فرستیم
        try:
            await client.send_message(message.chat.id, text)
        except:
            pass

# کلاینت اصلی
app = Client("khan_master", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)

@app.on_message(filters.me & ~filters.forwarded)
async def handle_cmds(client, message):
    global TIME_NAME_ACTIVE
    if not message.text: return
    
    cmd = message.text.strip().lower()
    chat_id = message.chat.id

    # پینگ
    if cmd == "پینگ":
        await safe_edit(client, message, "🚀 **سیستم آنلاین و پاسخگو است.**")

    # آمار
    elif cmd == "آمار":
        await safe_edit(client, message, f"📊 تعداد اکانت‌های فعال: `{len(active_clients) + 1}`")

    # ساعت
    elif cmd == "ساعت":
        t = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
        await safe_edit(client, message, f"🇮🇷 ساعت: `{t}`")

    # لاگین
    elif message.reply_to_message and cmd == "لاگین":
        raw_phone = message.reply_to_message.text.strip()
        clean_phone = re.sub(r'[^\d]', '', raw_phone)
        if clean_phone.startswith('0'): clean_phone = '98' + clean_phone[1:]
        
        await safe_edit(client, message, f"⏳ ارسال کد برای `{clean_phone}`...")
        
        tmp = Client(":memory:", api_id=API_ID, api_hash=API_HASH)
        try:
            await tmp.connect()
            code_data = await tmp.send_code(clean_phone)
            pending_logins[chat_id] = {"phone": clean_phone, "hash": code_data.phone_code_hash, "client": tmp}
            await safe_edit(client, message, "✅ کد ارسال شد.\nحالا روی کد ۵ رقمی ریپلای کن و بفرست: `تایید`")
        except Exception as e:
            await safe_edit(client, message, f"❌ خطا: {str(e)}")

    # تایید
    elif message.reply_to_message and cmd == "تایید":
        info = pending_logins.get(chat_id)
        if not info:
            await safe_edit(client, message, "❌ ابتدا `لاگین` بزنید.")
            return
        
        otp = message.reply_to_message.text.strip()
        await safe_edit(client, message, "⏳ در حال تایید و ورود...")
        
        try:
            await info["client"].sign_in(info["phone"], info["hash"], otp)
            ss = await info["client"].export_session_string()
            me = await info["client"].get_me()
            
            save_session(me.id, ss)
            
            new_c = Client(f"sub_{me.id}", api_id=API_ID, api_hash=API_HASH, session_string=ss, in_memory=True)
            await new_c.start()
            active_clients[str(me.id)] = new_c
            
            await safe_edit(client, message, f"🎉 سلف‌بات برای `{me.first_name}` فعال شد!")
            del pending_logins[chat_id]
        except Exception as e:
            await safe_edit(client, message, f"❌ خطا: {str(e)}")

    # تایم اسم
    elif cmd == "تایم فعال":
        TIME_NAME_ACTIVE = True
        await safe_edit(client, message, "✅ اسم ساعتی روشن شد.")
    elif cmd == "تایم خاموش":
        TIME_NAME_ACTIVE = False
        await safe_edit(client, message, "❌ اسم ساعتی خاموش شد.")

# تسک پس‌زمینه ساعت
async def time_task():
    while True:
        if TIME_NAME_ACTIVE:
            try:
                now = datetime.now(IRAN_TZ).strftime("%H:%M")
                bold = "".join(["𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗:"[int(c) if c!=':' else 10] for c in now])
                await app.update_profile(first_name=f"{DEFAULT_NAME} ┃ {bold}")
            except: pass
        await asyncio.sleep(60)

# راه‌اندازی
async def start_all():
    print("در حال استارت اکانت اصلی...")
    await app.start()
    
    saved = load_sessions()
    for uid, ss in saved.items():
        try:
            c = Client(f"sub_{uid}", api_id=API_ID, api_hash=API_HASH, session_string=ss, in_memory=True)
            await c.start()
            active_clients[uid] = c
        except: pass
        
    asyncio.create_task(time_task())
    print("سلف‌بات با موفقیت روشن شد.")
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_all())
