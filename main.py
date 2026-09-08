import asyncio
import glob
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import static_ffmpeg
import yt_dlp
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait

# لود کردن ابزار FFMPEG
static_ffmpeg.add_paths()

# متغیرهای محیطی
api_id = int(os.environ.get("API_ID", 0))
api_hash = os.environ.get("API_HASH", "")
session_string = os.environ.get("SESSION_STRING", "")

app = Client(
    name="my_account",
    api_id=api_id,
    api_hash=api_hash,
    session_string=session_string,
)

# تنظیمات اصلی
IRAN_TZ = ZoneInfo("Asia/Tehran")
US_TZ = ZoneInfo("America/New_York")
DEFAULT_NAME = "𝗞𝗛𝗔𝗡"
TIME_NAME_ACTIVE = False

# دیتابیس موقت برای ذخیره نتایج جستجو {chat_id: [results]}
pending_music_choices = {}

BOLD_DIGITS = {"0": "𝟎", "1": "𝟏", "2": "𝟐", "3": "𝟑", "4": "𝟒", "5": "𝟓", "6": "𝟔", "7": "𝟕", "8": "𝟖", "9": "𝟗", ":": ":"}
def to_bold_time(time_str: str) -> str: return "".join(BOLD_DIGITS.get(ch, ch) for ch in time_str)

PERSIAN_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
PERSIAN_WEEKDAYS = {"Saturday": "شنبه", "Sunday": "یکشنبه", "Monday": "دوشنبه", "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه", "Thursday": "پنج‌شنبه", "Friday": "جمعه"}

def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365: jy += (days - 1) // 365; days = (days - 1) % 365
    if days < 186: jm = 1 + (days // 31); jd = 1 + (days % 31)
    else: jm = 7 + ((days - 186) // 30); jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

# ─── تنظیمات یوتیوب ───
YT_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "geo_bypass": True,
    "extractor_args": {"youtube": {"player_client": ["ios", "android"]}},
    "http_headers": {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15"}
}

# 1. تابع جستجوی ۵ نتیجه برتر
def fetch_search_results(query: str, max_results=5):
    opts = YT_BASE_OPTS.copy()
    opts["extract_flat"] = True # فقط جستجو کن، دانلود نکن (برای سرعت)
    
    search_query = f"ytsearch{max_results}:{query}"
    results = []
    
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(search_query, download=False)
            if "entries" in info:
                for entry in info["entries"]:
                    results.append({
                        "title": entry.get("title", "Unknown"),
                        "url": entry.get("url"),
                        "duration": entry.get("duration", 0),
                        "uploader": entry.get("uploader", "YouTube")
                    })
        except Exception as e:
            print(f"Search Error: {e}")
    return results

# 2. تابع دانلود مستقیم از URL
def run_yt_download(url: str, is_audio: bool):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = YT_BASE_OPTS.copy()

    if is_audio:
        ydl_opts.update({
            "outtmpl": "downloads/%(title).50s.%(ext)s",
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        })
    else:
        ydl_opts.update({
            "outtmpl": "downloads/%(title).50s.%(ext)s",
            "format": "best[ext=mp4]/best",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        base = os.path.splitext(filename)[0]
        files = glob.glob(f"{glob.escape(base)}.*")
        return files[0] if files else filename, info.get("title", "Music")

# تابع دانلود و ارسال نهایی
async def download_and_send_url(message, url: str, is_audio: bool):
    try:
        await message.edit_text("⏳ **در حال دانلود فایل با بالاترین کیفیت...**")
        file_path, title = await asyncio.to_thread(run_yt_download, url, is_audio)

        if not file_path or not os.path.exists(file_path):
            await message.edit_text("❌ **خطا در دانلود فایل!**")
            return

        await message.edit_text("📤 **دانلود شد! در حال آپلود...**")

        if is_audio or file_path.endswith(".mp3"):
            await message.reply_audio(audio=file_path, title=title[:50], caption=f"🎵 **{title}**")
        else:
            await message.reply_video(video=file_path, caption=f"🎬 **{title}**")

        await message.delete()
        if os.path.exists(file_path): os.remove(file_path)

    except Exception as e:
        await message.edit_text(f"❌ **خطا:**\n`{str(e)[:100]}`")

# ─── تسک اسم ساعتی ───
async def auto_time_name_task():
    global TIME_NAME_ACTIVE
    last_time = ""
    while True:
        if TIME_NAME_ACTIVE:
            try:
                now = datetime.now(IRAN_TZ).strftime("%H:%M")
                if now != last_time:
                    await app.update_profile(first_name=f"{DEFAULT_NAME} ┃ {to_bold_time(now)}")
                    last_time = now
            except FloodWait as e: await asyncio.sleep(e.value)
            except: pass
        await asyncio.sleep(15)

# ─── دریافت دستورات ───
@app.on_message(filters.me & ~filters.forwarded)
async def handle_commands(client, message):
    global TIME_NAME_ACTIVE
    if not message.text: return

    text = message.text.strip()
    lower_text = text.lower()
    chat_id = message.chat.id

    # 1. پردازش انتخاب عدد از لیست جستجو (۱ تا ۵)
    if text.isdigit() and message.reply_to_message:
        if chat_id in pending_music_choices:
            choice = int(text) - 1 # تبدیل 1 به ایندکس 0
            results = pending_music_choices[chat_id]
            
            if 0 <= choice < len(results):
                selected_url = results[choice]["url"]
                # پاک کردن لیست از حافظه
                del pending_music_choices[chat_id]
                # دانلود و ارسال
                await download_and_send_url(message, selected_url, is_audio=True)
                return
            else:
                await message.edit_text("❌ **عدد وارد شده در لیست وجود ندارد!**")
                return

    # 2. جستجوی هوشمند آهنگ
    if lower_text.startswith("اهنگ ") or lower_text.startswith("آهنگ "):
        query = text.split(maxsplit=1)[1].strip()
        await message.edit_text(f"🔍 **در حال جستجوی دقیق برای:** `{query}`...")
        
        # جستجو در یوتیوب (۵ نتیجه 
