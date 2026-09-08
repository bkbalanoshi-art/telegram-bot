import asyncio
import os
import json
import re
import static_ffmpeg
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, idle
from pyrogram.errors import RPCError, FloodWait, PeerIdInvalid

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

# --- تابع "اتمی" برای حل مشکل Peer ID ---
async def safe_edit(client, message, text):
    """این تابع به جای ادیت، پیام جدید می‌فرستد تا باگ Peer ID را دور بزند"""
    try:
        # ۱. ابتدا پیام جدید را می‌فرستیم (این کار هویت چت را لود می‌کند)
        await client.send_message(message.chat.id, text)
        # ۲. سپس پیام قبلی (دستور) را پاک می‌کنیم
        await message.delete()
    except Exception as e:
        print(f"Edit Error: {e}")

# کلاینت اصلی
app = Client(
    "khan_master", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    session_string=SESSION_STRING, 
    in_memory=True
)

@app.on_message(~filters.forwarded)
async def handle_everything(client, message):
    global TIME_NAME_ACTIVE
    
    # فقط اگر خودم پیام فرستادم پردازش کن
    if not message.from_user or not message.from_user.is_self:
        return
    if not message.text:
        return

    text = message.text.strip()
    cmd = text.lower()
    chat_id = message.chat.id

    try:
        # دستورات
        if cmd == "پینگ":
            await safe_edit(client, message, "🚀 **سلف‌بات خان فعال است.**")

        elif cmd == "آمار":
            await safe_edit(client, message, f"📊 تعداد اکانت‌های فعال: `{len(active_clients) + 1}`")

        elif cmd == "ساعت":
            t = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
            await safe_edit(client, message, f"🇮🇷 ساعت ایران: `{t}`")

        # لاگین
        elif message.reply_to_message and cmd == "لاگین":
            raw_phone = message.reply_to_message.text.strip()
            clean_phone = re.sub(r'[^\d]', '', raw_phone)
            if clean_phone.startswith('0'): clean_phone = '98' + clean_phone[1:]
            
            await safe_edit(client, message, f"⏳ ارسال کد برای `{clean_phone}`...\n(کد را با **فاصله** بفرستید)")
            
            tmp = Client(":memory:", api_id=API_ID, api_hash=API_HASH)
            try:
                await tmp.connect()
                code_data = await tmp.send_code(clean_phone)
                pending_logins[chat_id] = {"phone": clean_phone, "hash": code_data.phone_code_hash, "client": tmp}
                await client.send_message(chat_id, "✅ کد ارسال شد. روی کد ریپلای کن و بگو: `تایید`")
            except Exception as e:
                await client.send_message(chat_id, f"❌ خطا در لاگین: {e}")

        # تایید
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
                
                # استارت اکانت مشتری
                new_c = Client(f"sub_{me.id}", api_id=API_ID, api_hash=API_HASH, session_string=ss, in_memory=True)
                await new_c.start()
                active_clients[str(me.id)] = new_c
                
                await client.send_message(chat_id, f"🎉 سلف‌بات روی `{me.first_name}` فعال شد!")
                del pending_logins[chat_id]
            except Exception as e:
                await client.send_message(chat_id, f"❌ خطا در تایید: {e}")

        # اضافه کردن سشن
        elif cmd.startswith("اضافه "):
            new_ss = text.split(maxsplit=1)[1].strip()
            try:
                new_c = Client(":memory:", api_id=API_ID, api_hash=API_HASH, session_string=new_ss)
                await new_c.start()
                me = await new_c.get_me()
                save_session(me.id, new_ss)
                active_clients[str(me.id)] = new_c
                await safe_edit(client, message, f"✅ اکانت `{me.first_name}` اضافه شد.")
            except Exception as e:
                await safe_edit(client, message, f"❌ سشن نامعتبر: {e}")

        # تایم اسم
        elif cmd == "تایم فعال":
            TIME_NAME_ACTIVE = True
            await safe_edit(client, message, "✅ تایم اسم روشن شد.")
        elif cmd == "تایم خاموش":
            TIME_NAME_ACTIVE = False
            await safe_edit(client, message, "❌ تایم اسم خاموش شد.")

    except (PeerIdInvalid, ValueError):
        # این بخش برای گرفتن ارور Peer ID و جلوگیری از کرش کردن
        try:
            await client.send_message(chat_id, "⚠️ خطای هویت چت رخ داد. مجدداً تلاش کنید.")
        except: pass

# تسک پس‌زمینه ساعت
async def time_bg():
    while True:
        if TIME_NAME_ACTIVE:
            try:
                now = datetime.now(IRAN_TZ).strftime("%H:%M")
                bold = "".join(["𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗:"[int(c) if c!=':' else 10] for c in now])
                await app.update_profile(first_name=f"{DEFAULT_NAME} ┃ {bold}")
            except: pass
        await asyncio.sleep(60)

# استارت‌آپ
async def main():
    print("Starting Master Account...")
    await app.start()
    
    # لود سشن‌های قبلی
    saved = load_sessions()
    for uid, ss in saved.items():
        try:
            c = Client(f"sub_{uid}", api_id=API_ID, api_hash=API_HASH, session_string=ss, in_memory=True)
            await c.start()
            active_clients[uid] = c
            print(f"Sub-Account {uid} Started.")
        except: pass
        
    asyncio.create_task(time_bg())
    print("System is Online!")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
