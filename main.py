import asyncio
import os
import json
import re
import static_ffmpeg
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, PhoneCodeExpired, PhoneCodeInvalid, SessionPasswordNeeded

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

app = Client("khan_master", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

@app.on_message(filters.me)
async def handle_cmds(client, message):
    global TIME_NAME_ACTIVE
    if not message.text: return
    
    cmd = message.text.strip().lower()
    chat_id = message.chat.id

    # پینگ
    if cmd == "پینگ":
        await message.edit_text("🚀 **سیستم آنلاین است.**")

    # آمار
    elif cmd == "آمار":
        await message.edit_text(f"📊 اکانت‌های فعال: `{len(active_clients) + 1}`")

    # ساعت
    elif cmd == "ساعت":
        t = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
        await message.edit_text(f"🇮🇷 ساعت: `{t}`")

    # --- لاگین (با اصلاح خودکار شماره) ---
    elif message.reply_to_message and cmd == "لاگین":
        raw_phone = message.reply_to_message.text.strip()
        
        # تمیز کردن شماره: حذف +، فاصله، پرانتز و خط تیره
        clean_phone = re.sub(r'[^\d]', '', raw_phone)
        
        # اگر شماره با 0 شروع میشه، حذفش کن و 98 اضافه کن (برای ایران)
        if clean_phone.startswith('0'):
            clean_phone = '98' + clean_phone[1:]
        elif not clean_phone.startswith('98'):
            # اگر کد کشور دیگری دارد، فرض را بر درستی می‌گذاریم، ولی بهتر است کاربر اصلاح کند
            pass 

        await message.edit_text(f"⏳ ارسال کد برای `{clean_phone}`...")
        
        tmp = Client(":memory:", api_id=API_ID, api_hash=API_HASH)
        try:
            await tmp.connect()
            code_data = await tmp.send_code(clean_phone)
            pending_logins[chat_id] = {"phone": clean_phone, "hash": code_data.phone_code_hash, "client": tmp}
            await message.edit_text("✅ کد ارسال شد.\nحالا روی کد ریپلای کن و بگو: `تایید`")
        except Exception as e:
            await message.edit_text(f"❌ خطا: {str(e)}\n\n💡 نکته: شماره باید بدون + و فاصله باشد.\nمثال: `989123456789`")

    # --- تایید ---
    elif message.reply_to_message and cmd == "تایید":
        info = pending_logins.get(chat_id)
        if not info:
            await message.edit_text("❌ ابتدا دستور `لاگین` را روی شماره بزنید.")
            return
        
        code = message.reply_to_message.text.strip()
        await message.edit_text("⏳ در حال ورود...")
        
        try:
            await info["client"].sign_in(info["phone"], info["hash"], code)
            ss = await info["client"].export_session_string()
            me = await info["client"].get_me()
            
            save_session(me.id, ss)
            
            new_c = Client(f"sub_{me.id}", API_ID, API_HASH, session_string=ss)
            await new_c.start()
            active_clients[str(me.id)] = new_c
            
            await message.edit_text(f"🎉 سلف‌بات برای `{me.first_name}` فعال شد!")
            del pending_logins[chat_id]
        except Exception as e:
            await message.edit_text(f"❌ خطا: {str(e)}")

    # اسم ساعتی
    elif cmd == "تایم فعال":
        TIME_NAME_ACTIVE = True
        await message.edit_text("✅ روشن شد.")
    elif cmd == "تایم خاموش":
        TIME_NAME_ACTIVE = False
        await message.edit_text("❌ خاموش شد.")

async def time_task():
    while True:
        if TIME_NAME_ACTIVE:
            try:
                now = datetime.now(IRAN_TZ).strftime("%H:%M")
                bold = "".join(["𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗:"[int(c) if c!=':' else 10] for c in now])
                await app.update_profile(first_name=f"{DEFAULT_NAME} ┃ {bold}")
            except: pass
        await asyncio.sleep(60)

async def main():
    await app.start()
    saved = load_sessions()
    for uid, ss in saved.items():
        try:
            c = Client(f"sub_{uid}", API_ID, API_HASH, session_string=ss)
            await c.start()
            active_clients[uid] = c
        except: pass
    asyncio.create_task(time_task())
    print("System Ready.")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
