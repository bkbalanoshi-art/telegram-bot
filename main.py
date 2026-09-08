import asyncio
import os
import json
import re
import urllib.parse
import urllib.request
import glob
from datetime import datetime
from zoneinfo import ZoneInfo
import static_ffmpeg
import yt_dlp
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait

# فعال‌سازی FFMPEG
static_ffmpeg.add_paths()

# تنظیمات اصلی Railway
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

app = Client("khan_self", API_ID, API_HASH, session_string=SESSION_STRING)

# تنظیمات زمانی و دیتابیس موقت
IRAN_TZ = ZoneInfo("Asia/Tehran")
DEFAULT_NAME = "𝗞𝗛𝗔𝗡"
TIME_NAME_ACTIVE = False
pending_music_choices = {}
PERSIAN_TO_ENG = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')

# کلمات کلیدی
MUSIC_PREFIXES = ("اهنگ ", "آهنگ ", "موزیک ", "ترانه ", "ریمیکس ", "دانلود آهنگ ", "دانلود اهنگ ", "صوتی ")

# ─── موتور جستجوی قدرتمند و بدون بلاک ───
def search_music_invidious(query, max_results=10):
    """جستجو در یوتیوب از طریق APIهای واسطه بدون ارور Client ID یا بلاکی"""
    encoded_query = urllib.parse.quote(query)
    # لیست سرورهای کمکی برای جستجو
    api_servers = [
        "https://inv.tux.pizza/api/v1/search",
        "https://invidious.nerdvpn.de/api/v1/search",
        "https://invidious.flokinet.to/api/v1/search"
    ]
    
    results = []
    for api_url in api_servers:
        try:
            full_url = f"{api_url}?q={encoded_query}&type=video"
            req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for item in data:
                    if len(results) >= max_results: break
                    results.append({
                        "title": item.get("title", "Music"),
                        "url": f"https://www.youtube.com/watch?v={item.get('videoId')}",
                        "duration": item.get("lengthSeconds", 0),
                        "uploader": item.get("author", "YouTube")
                    })
                if results: return results
        except: continue
    return results

# ─── دانلودر اختصاصی موبایل ───
def run_yt_download(url, is_audio):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        "quiet": True, "no_warnings": True, "nocheckcertificate": True,
        "extractor_args": {"youtube": {"player_client": ["android", "ios"]}},
        "http_headers": {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko)"}
    }
    if is_audio:
        ydl_opts.update({
            "outtmpl": "downloads/%(title).50s.%(ext)s",
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        })
    else:
        ydl_opts.update({"outtmpl": "downloads/%(title).50s.%(ext)s", "format": "best[ext=mp4]/best"})

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        if is_audio: path = os.path.splitext(path)[0] + ".mp3"
        return path, info.get("title", "Music")

# ─── هندلر دستورات ───
@app.on_message(filters.me & ~filters.forwarded)
async def main_handler(client, message):
    global TIME_NAME_ACTIVE
    if not message.text: return
    
    text = message.text.strip()
    chat_id = message.chat.id
    clean_text = text.translate(PERSIAN_TO_ENG)

    # ۱. پردازش انتخاب عدد (ریپلای)
    if clean_text.isdigit() and message.reply_to_message and chat_id in pending_music_choices:
        idx = int(clean_text) - 1
        res_list = pending_music_choices[chat_id]
        if 0 <= idx < len(res_list):
            target_url = res_list[idx]["url"]
            del pending_music_choices[chat_id]
            await message.edit_text("⏳ **در حال دانلود با بالاترین کیفیت...**")
            try:
                path, title = await asyncio.to_thread(run_yt_download, target_url, True)
                await message.edit_text("📤 **در حال آپلود...**")
                await message.reply_audio(path, caption=f"🎵 **{title}**")
                await message.delete()
                if os.path.exists(path): os.remove(path)
            except Exception as e:
                await message.edit_text(f"❌ خطا در دانلود: {e}")
        return

    # ۲. جستجوی موزیک
    prefix = next((p for p in MUSIC_PREFIXES if text.lower().startswith(p)), None)
    if prefix:
        query = text[len(prefix):].strip()
        if not query: return
        await message.edit_text(f"🔍 **در حال جستجوی دقیق برای:** `{query}`...")
        
        results = await asyncio.to_thread(search_music_invidious, query, 10)
        if not results:
            await message.edit_text("❌ متأسفانه نتیجه‌ای یافت نشد.")
            return
            
        pending_music_choices[chat_id] = results
        msg = f"🎧 **نتایج ۱۰ تایی برای:** `{query}`\n\n"
        for i, r in enumerate(results):
            dur = f"{r['duration']//60}:{r['duration']%60:02d}" if r['duration'] else "??:??"
            msg += f"**{i+1}.** `{r['title'][:40]}` | `{dur}`\n"
        msg += "\n👇 **عدد مورد نظر را روی این پیام ریپلای کنید.**"
        await message.edit_text(msg)
        return

    # ۳. دستورات جانبی
    if text.lower() == "پنل":
        await message.edit_text("╭───「 👑 **𝗞𝗛𝗔𝗡 𝗦𝗘𝗟𝗙** 」\n│\n├ 🎵 `اهنگ <نام>`\n├ 🎬 `ویدیو <نام>`\n├ 👤 `تایم فعال / خاموش`\n╰──────────")
    elif text == "تایم فعال":
        TIME_NAME_ACTIVE = True
        await message.edit_text("✅ اسم ساعتی روشن شد.")
    elif text == "تایم خاموش":
        TIME_NAME_ACTIVE = False
        await message.edit_text("❌ اسم ساعتی خاموش شد.")

# ─── تسک ساعت و استارت ───
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
    asyncio.create_task(time_task())
    print("KHAN SELF ONLINE")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
