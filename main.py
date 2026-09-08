import asyncio
import glob
import os
import re
import json
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
import static_ffmpeg
import yt_dlp

# ─── 🛠 رفع قطعی و نهایی باگ Peer ID برای آیدی‌های جدید تلگرام ───
import pyrogram.utils

# افزایش محدودیت‌های داخلی کتابخانه برای پذیرش آیدی‌های بزرگ جدید
pyrogram.utils.MIN_CHANNEL_ID = -100999999999999
pyrogram.utils.MIN_CHAT_ID = -99999999999999
pyrogram.utils.MAX_USER_ID = 99999999999999

def patched_get_peer_type(peer_id: int) -> str:
    if peer_id > 0:
        return "user"
    if str(peer_id).startswith("-100"):
        return "channel"
    return "chat"

# جایگزین کردن تابع اصلی کتابخانه با تابع اصلاح‌شده ما
pyrogram.utils.get_peer_type = patched_get_peer_type
# ─────────────────────────────────────────────────────────────

from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, PeerIdInvalid, RPCError

# فعال‌سازی FFMPEG برای دانلودر
static_ffmpeg.add_paths()

# متغیرهای Railway
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()

app = Client("khan_self", API_ID, API_HASH, session_string=SESSION_STRING)

# تنظیمات
IRAN_TZ = ZoneInfo("Asia/Tehran")
DEFAULT_NAME = "𝗞𝗛𝗔𝗡"
TIME_NAME_ACTIVE = False
pending_music_choices = {}
PERSIAN_TO_ENG = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
BOLD_DIGITS = {"0": "𝟎", "1": "𝟏", "2": "𝟐", "3": "𝟑", "4": "𝟒", "5": "𝟓", "6": "𝟔", "7": "𝟕", "8": "𝟖", "9": "𝟗", ":": ":"}

def to_bold_time(t): return "".join(BOLD_DIGITS.get(c, c) for c in t)

MUSIC_PREFIXES = ("اهنگ ", "آهنگ ", "موزیک ", "ترانه ", "ریمیکس ", "دانلود آهنگ ", "دانلود اهنگ ", "صوتی ")

# ─── تابع ارسال و ادیت امن ───
async def safe_edit(client, message, text):
    try:
        await message.edit_text(text)
    except Exception:
        try:
            await client.send_message(message.chat.id, text)
            try: await message.delete()
            except: pass
        except: pass

# ─── موتور جستجوی هوشمند آهنگ ───
def search_music_engine(query: str, max_results=10):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        "quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True,
        "nocheckcertificate": True, "geo_bypass": True,
        "extractor_args": {"youtube": {"player_client": ["android", "ios"]}},
        "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    }
    results = []
    seen_urls = set()
    search_queries = [f"ytmusicsearch{max_results}:{query}", f"ytsearch{max_results}:{query}"]

    for sq in search_queries:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(sq, download=False)
                if info and "entries" in info:
                    for entry in info["entries"]:
                        url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry.get('id')}"
                        if url not in seen_urls:
                            seen_urls.add(url)
                            results.append({
                                "title": entry.get("title", "Music"),
                                "url": url,
                                "duration": int(entry.get("duration") or 0),
                                "uploader": entry.get("uploader") or "Artist"
                            })
                        if len(results) >= max_results: break
        except: continue
        if len(results) >= max_results: break
    return results

# ─── دانلودر ───
def run_yt_download(url: str, is_audio: bool):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        "quiet": True, "no_warnings": True, "nocheckcertificate": True,
        "extractor_args": {"youtube": {"player_client": ["android"]}},
        "http_headers": {"User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36"}
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
        filename = ydl.prepare_filename(info)
        if is_audio: filename = os.path.splitext(filename)[0] + ".mp3"
        return filename, info.get("title", "Music")

# ─── هندلر پیام‌ها ───
@app.on_message(filters.me & ~filters.forwarded)
async def main_handler(client, message):
    global TIME_NAME_ACTIVE
    if not message.text: return
    text = message.text.strip()
    chat_id = message.chat.id
    clean_text = text.translate(PERSIAN_TO_ENG)

    # انتخاب عدد از لیست (ریپلای)
    if clean_text.isdigit() and message.reply_to_message and chat_id in pending_music_choices:
        idx = int(clean_text) - 1
        res_list = pending_music_choices[chat_id]
        if 0 <= idx < len(res_list):
            url = res_list[idx]["url"]
            del pending_music_choices[chat_id]
            await safe_edit(client, message, "⏳ **در حال دانلود...**")
            try:
                path, title = await asyncio.to_thread(run_yt_download, url, True)
                await message.reply_audio(path, caption=f"🎵 **{title}**")
                await message.delete()
                if os.path.exists(path): os.remove(path)
            except Exception as e: await safe_edit(client, message, f"❌ خطا: {e}")
        return

    # جستجوی آهنگ
    matched = next((p for p in MUSIC_PREFIXES if text.lower().startswith(p)), None)
    if matched:
        query = text[len(matched):].strip()
        await safe_edit(client, message, f"🔍 **در حال جستجو:** `{query}`...")
        results = await asyncio.to_thread(search_music_engine, query, 10)
        if not results:
            await safe_edit(client, message, "❌ نتیجه‌ای یافت نشد.")
            return
        pending_music_choices[chat_id] = results
        msg = f"🎧 **نتایج ۱۰ تایی:** `{query}`\n\n"
        for i, r in enumerate(results):
            msg += f"**{i+1}.** `{r['title'][:40]}` | `{r['duration']//60}:{r['duration']%60:02d}`\n"
        msg += "\n👇 **عدد را ریپلای کنید.**"
        await safe_edit(client, message, msg)
        return

    # دستورات پایه
    if text.lower() == "پینگ": await safe_edit(client, message, "🚀 **آنلاین**")
    elif text.lower() == "پنل": await safe_edit(client, message, "╭───「 👑 **𝗞𝗛𝗔𝗡 𝗦𝗘𝗟𝗙** 」\n│\n├ 🎵 `اهنگ <نام>`\n├ ⏱ `ساعت`\n├ 👤 `تایم فعال / خاموش`\n╰──────────")
    elif text == "تایم فعال": 
        TIME_NAME_ACTIVE = True
        await safe_edit(client, message, "✅ روشن")
    elif text == "تایم خاموش":
        TIME_NAME_ACTIVE = False
        await app.update_profile(first_name=DEFAULT_NAME)
        await safe_edit(client, message, "❌ خاموش")
    elif text == "ساعت":
        await safe_edit(client, message, f"⏰ ساعت: `{datetime.now(IRAN_TZ).strftime('%H:%M:%S')}`")

async def time_task():
    while True:
        if TIME_NAME_ACTIVE:
            try:
                now = datetime.now(IRAN_TZ).strftime("%H:%M")
                await app.update_profile(first_name=f"{DEFAULT_NAME} ┃ {to_bold_time(now)}")
            except: pass
        await asyncio.sleep(60)

async def main():
    await app.start()
    asyncio.create_task(time_task())
    print("--- KHAN SELF IS READY ---")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
