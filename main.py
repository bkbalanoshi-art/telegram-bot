import asyncio
import glob
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import static_ffmpeg
import yt_dlp
from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler
from pyrogram.errors import (
    FloodWait,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    SessionPasswordNeeded,
)

# تنظیمات اصلی
static_ffmpeg.add_paths()
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
SESSIONS_FILE = "sessions.json"

active_clients = {}  # {user_id: client_instance}
pending_logins = {}  # {chat_id: login_data}

IRAN_TZ = ZoneInfo("Asia/Tehran")
US_TZ = ZoneInfo("America/New_York")
DEFAULT_NAME = "𝗞𝗛𝗔𝗡"
TIME_NAME_ACTIVE = False

# --- توابع کمکی ---

def load_saved_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                return json.load(f)
        except: return {}
    return {}

def save_session_to_file(user_id, session_str):
    data = load_saved_sessions()
    data[str(user_id)] = session_str
    with open(SESSIONS_FILE, "w") as f:
        json.dump(data, f)

def run_yt_download(query, is_audio):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        'format': 'bestaudio/best' if is_audio else 'best[ext=mp4]/best',
        'outtmpl': 'downloads/%(title).50s.%(ext)s',
        'quiet': True, 'no_warnings': True,
    }
    if is_audio:
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        q = query if query.startswith("http") else f"ytsearch1:{query}"
        info = ydl.extract_info(q, download=True)
        filename = ydl.prepare_filename(info['entries'][0] if 'entries' in info else info)
        if is_audio: filename = os.path.splitext(filename)[0] + ".mp3"
        return filename, info.get('title', 'File')

async def download_and_send(client, message, query, is_audio=False):
    await message.edit_text("⏳ **در حال دانلود...**")
    try:
        path, title = await asyncio.to_thread(run_yt_download, query, is_audio)
        await message.edit_text("📤 **در حال آپلود...**")
        if is_audio: await message.reply_audio(path, caption=f"🎵 **{title}**")
        else: await message.reply_video(path, caption=f"🎬 **{title}**")
        await message.delete()
        if os.path.exists(path): os.remove(path)
    except Exception as e:
        await message.edit_text(f"❌ خطا: {e}")

# --- هندلر دستورات سلف‌بات ---

async def handle_commands(client, message):
    if not message.text or not message.from_user or not message.from_user.is_self:
        return
    
    text = message.text.strip()
    l_text = text.lower()

    if l_text in ["پنل", "panel"]:
        await message.edit_text("╭───「 👑 **𝗞𝗛𝗔𝗡 𝗦𝗘𝗟𝗙** 」\n│\n├ 🎵 `اهنگ <اسم>`\n├ 🎬 `ویدیو <اسم>`\n├ ⏱ `ساعت` | `تاریخ` | `زمان`\n├ 👤 `تایم فعال` | `تایم خاموش`\n╰──────────")

    elif l_text.startswith("اهنگ "):
        await download_and_send(client, message, text[5:], True)
    
    elif l_text.startswith("ویدیو "):
        await download_and_send(client, message, text[6:], False)

    elif l_text == "ساعت":
        t = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
        await message.edit_text(f"🇮🇷 ساعت ایران: `{t}`")

    elif text == "تایم فعال":
        global TIME_NAME_ACTIVE
        TIME_NAME_ACTIVE = True
        await message.edit_text("✅ اسم ساعتی فعال شد.")

# --- هندلر مدیریت مشتریان (فقط برای صاحب بات) ---

async def handle_master(client, message):
    if not message.text or not message.from_user or not message.from_user.is_self:
        return
    
    text = message.text.strip()

    if message.reply_to_message and text == "لاگین":
        phone = message.reply_to_message.text.strip()
        await message.edit_text(f"⏳ ارسال کد برای `{phone}`...")
        tmp = Client(":memory:", API_ID, API_HASH)
        await tmp.connect()
        try:
            sent_code = await tmp.send_code(phone)
            pending_logins[message.chat.id] = {"phone": phone, "hash": sent_code.phone_code_hash, "client": tmp}
            await message.edit_text("✅ کد ارسال شد. روی کد ریپلای کنید و بگویید: `تایید`")
        except Exception as e:
            await message.edit_text(f"❌ خطا: {e}")

    elif message.reply_to_message and text == "تایید":
        data = pending_logins.get(message.chat.id)
        if not data: return
        code = message.reply_to_message.text.strip()
        await message.edit_text("⏳ در حال فعال‌سازی...")
        try:
            await data["client"].sign_in(data["phone"], data["hash"], code)
            s_str = await data["client"].export_session_string()
            me = await data["client"].get_me()
            
            # استارت سلف جدید
            new_cli = Client(f"sub_{me.id}", API_ID, API_HASH, session_string=s_str)
            new_cli.add_handler(MessageHandler(handle_commands))
            await new_cli.start()
            
            active_clients[str(me.id)] = new_cli
            save_session_to_file(me.id, s_str)
            await message.edit_text(f"🎉 سلف‌بات برای `{me.first_name}` فعال شد!")
            del pending_logins[message.chat.id]
        except Exception as e:
            await message.edit_text(f"❌ خطا: {e}")

    elif text == "آمار":
        await message.edit_text(f"📊 تعداد سلف‌بات‌های فعال: `{len(active_clients)}`")

# --- استارت‌آپ ---

async def main():
    print("در حال راه‌اندازی سلف‌بات اصلی...")
    master = Client("master", API_ID, API_HASH, session_string=SESSION_STRING)
    master.add_handler(MessageHandler(handle_commands))
    master.add_handler(MessageHandler(handle_master))
    
    await master.start()
    active_clients["master"] = master
    
    # لود سشن‌های قبلی
    saved = load_saved_sessions()
    for uid, s_str in saved.items():
        try:
            c = Client(f"sub_{uid}", API_ID, API_HASH, session_string=s_str)
            c.add_handler(MessageHandler(handle_commands))
            await c.start()
            active_clients[uid] = c
            print(f"اکانت {uid} متصل شد.")
        except: print(f"خطا در اتصال اکانت {uid}")

    print("پلتفرم با موفقیت روشن شد.")
    
    # تسک ساعت
    async def time_task():
        while True:
            if TIME_NAME_ACTIVE:
                try:
                    now = datetime.now(IRAN_TZ).strftime("%H:%M")
                    bold = "".join(["𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗:"[int(c) if c!=':' else 10] for c in now])
                    await master.update_profile(first_name=f"{DEFAULT_NAME} ┃ {bold}")
                except: pass
            await asyncio.sleep(60)

    asyncio.create_task(time_task())
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
