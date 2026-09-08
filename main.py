import asyncio
import os
import json
import re
import static_ffmpeg
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, idle
from pyrogram.errors import RPCError, FloodWait, PeerIdInvalid

# تنظیمات اصلی
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

# --- تابع طلایی برای حل مشکل ID not found و Peer ID ---
async def safe_action(client, chat_id, text, message=None):
    """این تابع ابتدا چت را شناسایی کرده و سپس پیام می‌فرستد"""
    try:
        # اجبار پایروگرام به پیدا کردن هویت چت از سرور تلگرام
        await client.get_chat(chat_id)
        if message:
            try:
                await message.edit_text(text)
            except:
                await client.send_message(chat_id, text)
        else:
            await client.send_message(chat_id, text)
    except Exception as e:
        # اگر باز هم نشد، یک پیام جدید می‌فرستیم (راه حل آخر)
        try:
            await client.send_message(chat_id, text)
        except:
            print(f"Error in safe_action: {e}")

# کلاینت اصلی
app = Client(
    "khan_master", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    session_string=SESSION_STRING, 
    in_memory=True
)

@app.on_message(filters.me & ~filters.forwarded)
async def handle_everything(client, message):
    global TIME_NAME_ACTIVE
    if not message.text:
        return

    text = message.text.strip()
    cmd = text.lower()
    chat_id = message.chat.id

    try:
        # دستورات پایه
        if cmd == "پینگ":
            await safe_action(client, chat_id, "🚀 **سلف‌بات آنلاین و پاسخگو است.**", message)

        elif cmd == "ساعت":
            t = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
            await safe_action(client, chat_id, f"🇮🇷 ساعت ایران: `{t}`", message)

        elif cmd == "آمار":
            await safe_action(client, chat_id, f"📊 اکانت‌های فعال: `{len(active_clients) + 1}`", message)

        # --- بخش لاگین مشتری ---
        elif message.reply_to_message and cmd == "لاگین":
            raw_phone = message.reply_to_message.text.strip()
            clean_phone = re.sub(r'[^\d]', '', raw_phone)
            if clean_phone.startswith('0'): clean_phone = '98' + clean_phone[1:]
            
            await safe_action(client, chat_id, f"⏳ ارسال کد برای `{clean_phone}`...", message)
            
            tmp = Client(":memory:", api_id=API_ID, api_hash=API_HASH)
            try:
                await tmp.connect()
                code_data = await tmp.send_code(clean_phone)
                pending_logins[chat_id] = {"phone": clean_phone, "hash": code_data.phone_code_hash, "client": tmp}
                await client.send_message(chat_id, "✅ کد ارسال شد. حالا مشتری کد را با **فاصله** بفرستد و شما روی آن ریپلای کنید و بگویید: `تایید`")
            except Exception as e:
                await client.send_message(chat_id, f"❌ خطا: {e}")

        elif message.reply_to_message and cmd == "تایید":
            info = pending_logins.get(chat_id)
            if not info:
                await client.send_message(chat_id, "❌ ابتدا `لاگین` بزنید.")
                return
            
            otp = re.sub(r'[^\d]', '', message.reply_to_message.text.strip())
            await client.send_message(chat_id, "⏳ در حال ورود...")
            
            try:
                await info["client"].sign_in(info["phone"], info["hash"], otp)
                ss = await info["client"].export_session_string()
                me = await info["client"].get_me()
                save_session(me.id, ss)
                
                # استارت اکانت جدید
                new_c = Client(f"sub_{me.id}", api_id=API_ID, api_hash=API_HASH, session_string=ss, in_memory=True)
                await new_c.start()
                active_clients[str(me.id)] = new_c
                
                await client.send_message(chat_id, f"🎉 سلف‌بات روی `{me.first_name}` فعال شد!")
                del pending_logins[chat_id]
            except Exception as e:
                await client.send_message(chat_id, f"❌ خطا در تایید: {e}")

        # --- تایم اسم ---
        elif cmd == "تایم فعال":
            TIME_NAME_ACTIVE = True
            await safe_action(client, chat_id, "✅ اسم ساعتی روشن شد.", message)
        elif cmd == "تایم خاموش":
            TIME_NAME_ACTIVE = False
            await safe_action(client, chat_id, "❌ اسم ساعتی خاموش شد.", message)

    except KeyError:
        # حل مشکل ID NOT FOUND
        await client.get_chat(chat_id)
        await client.send_message(chat_id, "⚠️ هویت چت شناسایی شد. دوباره دستور را ارسال کنید.")

# تسک ساعت
async def time_bg():
    while True:
        if TIME_NAME_ACTIVE:
            try:
                now = datetime.now(IRAN_TZ).strftime("%H:%M")
                bold = "".join(["𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗:"[int(c) if c!=':' else 10] for c in now])
                await app.update_profile(first_name=f"{DEFAULT_NAME} ┃ {bold}")
            except: pass
        await asyncio.sleep(60)

# راه‌اندازی
async def main():
    print("در حال استارت اکانت اصلی...")
    await app.start()
    
    saved = load_sessions()
    for uid, ss in saved.items():
        try:
            c = Client(f"sub_{uid}", api_id=API_ID, api_hash=API_HASH, session_string=ss, in_memory=True)
            await c.start()
            active_clients[uid] = c
            print(f"اکانت {uid} فعال گشت.")
        except: pass
        
    asyncio.create_task(time_bg())
    print("سیستم آماده استفاده است.")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
