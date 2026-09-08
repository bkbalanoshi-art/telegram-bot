import asyncio
import glob
import json
import os
import urllib.parse
import urllib.request
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

# ─── موتور جستجوی اختصاصی و بدون بلاکی ───
def fetch_search_results_api(query: str, max_results=5):
    encoded_query = urllib.parse.quote(query)
    
    # سرورهای اختصاصی جستجوی بدون بلاک
    endpoints = [
        f"https://pipedapi.kavin.rocks/search?q={encoded_query}&filter=all",
        f"https://api.piped.private.coffee/search?q={encoded_query}&filter=all",
        f"https://inv.tux.pizza/api/v1/search?q={encoded_query}&type=video",
        f"https://invidious.nerdvpn.de/api/v1/search?q={encoded_query}&type=video",
    ]

    results = []
    seen_urls = set()

    for url in endpoints:
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    
                    # فرمت Piped API
                    if isinstance(data, dict) and "items" in data:
                        for item in data["items"]:
                            if item.get("type") == "stream":
                                v_url = "https://www.youtube.com" + item.get("url", "")
                                if v_url in seen_urls: continue
                                seen_urls.add(v_url)

                                results.append({
                                    "title": item.get("title", "Unknown"),
                                    "url": v_url,
                                    "duration": item.get("duration", 0),
                                    "uploader": item.get("uploaderName", "Music")
                                })
                                if len(results) >= max_results:
                                    return results

                    # فرمت Invidious API
                    elif isinstance(data, list):
                        for item in data:
                            if item.get("type") == "video":
                                v_id = item.get("videoId")
                                if not v_id: continue
                                v_url = f"https://www.youtube.com/watch?v={v_id}"
                                if v_url in seen_urls: continue
                                seen_urls.add(v_url)

                                results.append({
                                    "title": item.get("title", "Unknown"),
                                    "url": v_url,
                                    "duration": item.get("lengthSeconds", 0),
                                    "uploader": item.get("author", "Music")
                                })
                                if len(results) >= max_results:
                                    return results
        except Exception as e:
            print(f"Search API error: {e}")
            continue

    # اگر سرورهای فوق جواب ندادند، سوندکلاود پشتیبان
    if not results:
        try:
            opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"scsearch{max_results}:{query}", download=False)
                if info and "entries" in info:
                    for entry in info["entries"]:
                        if not entry: continue
                        u = entry.get("webpage_url") or entry.get("url")
                        if u and u not in seen_urls:
                            seen_urls.add(u)
                            results.append({
                                "title": entry.get("title", "Music"),
                                "url": u,
                                "duration": int(entry.get("duration") or 0),
                                "uploader": entry.get("uploader", "SoundCloud")
                            })
        except Exception as e:
            print(f"SoundCloud fallback error: {e}")

    return results

# ─── دانلودر مستقیم و بدون بلاک ───
def run_yt_download(url: str, is_audio: bool):
    os.makedirs("downloads", exist_ok=True)
    
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
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

# دانلود و ارسال در تلگرام
async def download_and_send_url(message, url: str, is_audio: bool):
    try:
        await message.edit_text("⏳ **در حال دانلود با کیفیت عالی...**")
        file_path, title = await asyncio.to_thread(run_yt_download, url, is_audio)

        if not file_path or not os.path.exists(file_path):
            await message.edit_text("❌ **خطا در دانلود فایل!**")
            return

        await message.edit_text("📤 **دانلود شد! در حال ارسال به تلگرام...**")

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

    # 1. انتخاب عدد از لیست ۵ تایی (ریپلای)
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
                await message.edit_text("❌ **شماره انتخابی در لیست نیست!**")
                return

    # 2. جستجوی پیشرفته آهنگ (بلوچی، کردی، ترکی، فارسی، خارجی و...)
    if lower_text.startswith("اهنگ ") or lower_text.startswith("آهنگ "):
        query = text.split(maxsplit=1)[1].strip()
        await message.edit_text(f"🔍 **در حال جستجو برای:** `{query}`...")
        
        results = await asyncio.to_thread(fetch_search_results_api, query, 5)
        
        if not results:
            await message.edit_text("❌ **هیچ موزیکی یافت نشد!**")
            return
            
        pending_music_choices[chat_id] = results
        
        msg = f"🎧 **نتایج پیدا شده برای:** `{query}`\n\n"
        for i, res in enumerate(results):
            dur = res['duration']
            dur_str = f"{dur//60}:{dur%60:02d}" if dur > 0 else "نامشخص"
            msg += f"**{i+1}.** `{res['title'][:45]}`\n🎙 {res['uploader'][:25]} ⏱ {dur_str}\n\n"
            
        msg += "👇 **روی همین پیام ریپلای کنید و شماره آن (مثلاً ۱ یا 1) را بفرستید.**"
        await message.edit_text(msg)
        return

    # 3. دانلود ویدیو
    elif lower_text.startswith("ویدیو "):
        query = text.split(maxsplit=1)[1].strip()
        await message.edit_text(f"🔍 **در حال جستجوی ویدیو...**")
        results = await asyncio.to_thread(fetch_search_results_api, query, 1)
        if results:
            await download_and_send_url(message, results[0]["url"], is_audio=False)
        else:
            await message.edit_text("❌ **ویدیویی یافت نشد.**")
        return

    # 4. دانلود مستقیم لینک
    elif lower_text.startswith("دانلود ") or lower_text.startswith("dl "):
        query = text.split(maxsplit=1)[1].strip()
        await download_and_send_url(message, query, is_audio=False)
        return

    # پنل و دستورات عمومی
    if lower_text in ["پنل", "منو"]:
        await message.edit_text(
            "╭───「 👑 **𝗞𝗛𝗔𝗡 𝗦𝗘𝗟𝗙** 」\n"
            "├ 🎵 `اهنگ <نام>` ➔ جستجوی موزیک\n"
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
    print("سلف‌بات خان با موتور جستجوی جدید بدون بلاکی فعال شد...")
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
