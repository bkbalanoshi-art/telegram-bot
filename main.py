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

# متغیرهای محیطی Railway
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

# تبدیل اعداد فارسی به انگلیسی
PERSIAN_TO_ENG = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')

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

# ─── موتور جستجوی هوشمند جدیدترین آهنگ‌ها (۱۰ تایی) ───
def search_music_multi_engine(query: str, max_results=10):
    results = []
    seen_urls = set()

    clean_q = query.strip()
    search_queries = []
    
    if "جدید" not in clean_q:
        search_queries.append(f"ytsearch15:آهنگ جدید {clean_q}")
        search_queries.append(f"ytsearch15:{clean_q} جدید")
    
    search_queries.append(f"ytsearch15:{clean_q}")
    search_queries.append(f"scsearch15:{clean_q}")

    yt_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "extractor_args": {"youtube": {"player_client": ["android", "ios", "mweb"]}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        }
    }

    for sq in search_queries:
        try:
            with yt_dlp.YoutubeDL(yt_opts) as ydl:
                info = ydl.extract_info(sq, download=False)
                if info and "entries" in info:
                    for entry in info["entries"]:
                        if not entry: continue
                        url = entry.get("url") or entry.get("webpage_url")
                        if not url and entry.get("id"):
                            url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            results.append({
                                "title": entry.get("title", "موزیک"),
                                "url": url,
                                "duration": int(entry.get("duration") or 0),
                                "uploader": entry.get("uploader") or entry.get("channel") or "Music"
                            })
                        if len(results) >= max_results:
                            break
        except Exception as e:
            print(f"Search query failed ({sq}): {e}")

        if len(results) >= max_results:
            break

    return results[:max_results]

# ─── دانلود مستقیم ───
def run_yt_download(url: str, is_audio: bool):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "extractor_args": {"youtube": {"player_client": ["android", "ios", "mweb"]}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
    }

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

# دانلود و ارسال فایل صوتی یا تصویری
async def download_and_send_url(message, url: str, is_audio: bool):
    try:
        await message.edit_text("⏳ **در حال دانلود فایل با بالاترین کیفیت...**")
        file_path, title = await asyncio.to_thread(run_yt_download, url, is_audio)

        if not file_path or not os.path.exists(file_path):
            await message.edit_text("❌ **خطا در دانلود فایل!**")
            return

        await message.edit_text("📤 **دانلود شد! در حال آپلود به تلگرام...**")

        if is_audio or file_path.endswith(".mp3"):
            await message.reply_audio(audio=file_path, title=title[:50], caption=f"🎵 **{title}**")
        else:
            await message.reply_video(video=file_path, caption=f"🎬 **{title}**")

        await message.delete()
        if os.path.exists(file_path): os.remove(file_path)

    except Exception as e:
        await message.edit_text(f"❌ **خطا در دریافت:**\n`{str(e)[:100]}`")

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

    # تبدیل اعداد فارسی به انگلیسی
    clean_digit_text = text.translate(PERSIAN_TO_ENG)

    # ۱. پاسخ به لیست انتخابی (۱ تا ۱۰)
    if clean_digit_text.isdigit() and message.reply_to_message:
        if chat_id in pending_music_choices:
            choice = int(clean_digit_text) - 1
            results = pending_music_choices[chat_id]
            
            if 0 <= choice < len(results):
                selected_url = results[choice]["url"]
                del pending_music_choices[chat_id]
                await download_and_send_url(message, selected_url, is_audio=True)
                return
            else:
                await message.edit_text("❌ **عدد انتخابی در لیست نیست!**")
                return

    # ۲. جستجوی جدیدترین موزیک‌ها (۱۰ تایی)
    if lower_text.startswith("اهنگ ") or lower_text.startswith("آهنگ "):
        query = text.split(maxsplit=1)[1].strip()
        await message.edit_text(f"🔍 **در حال جستجوی جدیدترین آهنگ‌های:** `{query}`...")
        
        results = await asyncio.to_thread(search_music_multi_engine, query, 10)
        
        if not results:
            await message.edit_text("❌ **متأسفانه هیچ موزیکی پیدا نشد!**\nلطفاً اسم آهنگ یا خواننده را بررسی کنید.")
            return
            
        pending_music_choices[chat_id] = results
        
        msg = f"🎧 **جدیدترین آهنگ‌های یافت‌شده برای:** `{query}`\n\n"
        for i, res in enumerate(results):
            dur = res['duration']
            dur_str = f"{dur//60}:{dur%60:02d}" if dur > 0 else "نامشخص"
            msg += f"**{i+1}.** `{res['title'][:45]}`\n🎙 {res['uploader'][:25]} ⏱ {dur_str}\n\n"
            
        msg += "👇 **کافیست روی همین پیام ریپلای کنید و شماره آن (مثلاً ۱ یا ۱۰) را بفرستید.**"
        await message.edit_text(msg)
        return

    # ۳. دانلود ویدیو
    elif lower_text.startswith("ویدیو "):
        query = text.split(maxsplit=1)[1].strip()
        await message.edit_text(f"🔍 **در حال جستجوی ویدیو...**")
        results = await asyncio.to_thread(search_music_multi_engine, query, 1)
        if results:
            await download_and_send_url(message, results[0]["url"], is_audio=False)
        else:
            await message.edit_text("❌ **ویدیویی یافت نشد.**")
        return

    # ۴. دانلود مستقیم از لینک
    elif lower_text.startswith("دانلود ") or lower_text.startswith("dl "):
        query = text.split(maxsplit=1)[1].strip()
        await download_and_send_url(message, query, is_audio=False)
        return

    # ۵. پنل راهنما و دستورات عمومی
    if lower_text in ["پنل", "منو", "panel"]:
        await message.edit_text(
            "╭───「 👑 **𝗞𝗛𝗔𝗡 𝗦𝗘𝗟𝗙** 」\n"
            "├ 🎵 `اهنگ <نام خواننده>` ➔ لیست ۱۰ تایی جدیدترین آهنگ‌ها\n"
            "├ 🎬 `ویدیو <نام>` ➔ دانلود ویدیو\n"
            "├ ⏱ `ساعت` | `تاریخ` | `زمان`\n"
            "├ 👤 `تایم فعال` | `تایم خاموش`\n"
            "╰───「 ⚡️ 𝑂𝑛𝑙𝑖𝑛𝑒 」"
        )
    elif lower_text == "ساعت":
        t = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
        await message.edit_text(f"⏰ ساعت: `{t}`")
    elif lower_text == "زمان":
        t = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
        now_iran = datetime.now(IRAN_TZ)
        jy, jm, jd = gregorian_to_jalali(now_iran.year, now_iran.month, now_iran.day)
        await message.edit_text(f"🗓 امروز: `{jd} {PERSIAN_MONTHS[jm-1]} {jy}`\n⏰ ساعت: `{t}`")
    elif text == "تایم فعال":
        TIME_NAME_ACTIVE = True
        await message.edit_text("✅ اسم ساعتی فعال شد.")
    elif text == "تایم خاموش":
        TIME_NAME_ACTIVE = False
        await app.update_profile(first_name=DEFAULT_NAME)
        await message.edit_text("❌ اسم ساعتی خاموش شد.")


async def main():
    await app.start()
    asyncio.create_task(auto_time_name_task())
    print("سلف‌بات خان با لیست ۱۰ تایی آهنگ‌ها فعال شد...")
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
