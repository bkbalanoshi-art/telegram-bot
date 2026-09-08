import asyncio
import glob
import json
import os
import re
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
DEFAULT_NAME = "𝗞𝗛𝗔𝗡"
TIME_NAME_ACTIVE = False

# دیتابیس موقت انتخاب‌ها
pending_music_choices = {}

# کلیدواژه‌های فارسی برای جستجو
MUSIC_PREFIXES = (
    "اهنگ ", "آهنگ ", "موزیک ", "ترانه ", "ریمیکس ", "رمیکس ",
    "دانلود اهنگ ", "دانلود آهنگ ", "دانلود موزیک ", "دانلود ترانه ",
    "دانلود ریمیکس ", "اهنگ جدید ", "آهنگ جدید ", "صوتی "
)

PERSIAN_TO_ENG = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
BOLD_DIGITS = {"0": "𝟎", "1": "𝟏", "2": "𝟐", "3": "𝟑", "4": "𝟒", "5": "𝟓", "6": "𝟔", "7": "𝟕", "8": "𝟖", "9": "𝟗", ":": ":"}
def to_bold_time(t): return "".join(BOLD_DIGITS.get(c, c) for c in t)

# ─── موتور جستجوی مستقیم و ۱۰۰٪ دقیق برای تمامی اقوام و زبان‌ها ───
def search_yt_direct(query: str, max_results=10):
    results = []
    seen_ids = set()

    # ۱. جستجوی مستقیم با پارسر اختصاصی یوتیوب
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={encoded_query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            match = re.search(r'var ytInitialData = ({.*?});</script>', html)
            if match:
                data = json.loads(match.group(1))
                contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
                for section in contents:
                    items = section.get('itemSectionRenderer', {}).get('contents', [])
                    for item in items:
                        v = item.get('videoRenderer')
                        if v and 'videoId' in v:
                            vid = v['videoId']
                            if vid in seen_ids: continue
                            seen_ids.add(vid)

                            title = v.get('title', {}).get('runs', [{}])[0].get('text', 'Music')
                            dur_str = v.get('lengthText', {}).get('simpleText', 'نامشخص')
                            uploader = v.get('ownerText', {}).get('runs', [{}])[0].get('text', 'Artist')

                            results.append({
                                "title": title,
                                "url": f"https://www.youtube.com/watch?v={vid}",
                                "duration": dur_str,
                                "uploader": uploader
                            })
                            if len(results) >= max_results: break
                    if len(results) >= max_results: break
    except Exception as e:
        print(f"Direct Search Exception: {e}")

    # ۲. در صورت لزوم، پشتیبان API Invidious
    if not results:
        try:
            api_url = f"https://api.invidious.io/api/v1/search?q={urllib.parse.quote(query)}&type=video"
            req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for item in data:
                    vid = item.get('videoId')
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        dur = item.get('lengthSeconds', 0)
                        dur_str = f"{dur//60}:{dur%60:02d}" if dur else "نامشخص"
                        results.append({
                            "title": item.get('title', 'Music'),
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "duration": dur_str,
                            "uploader": item.get('author', 'Artist')
                        })
                        if len(results) >= max_results: break
        except Exception as e:
            print(f"Invidious API Error: {e}")

    return results[:max_results]

# ─── دانلودر اختصاصی بدون بلاک آی‌پی ───
def run_yt_download(url: str, is_audio: bool):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "extractor_args": {"youtube": {"player_client": ["android", "ios"]}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Android 14; Mobile; rv:122.0) Gecko/122.0 Firefox/122.0"
        }
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
        base = os.path.splitext(filename)[0]
        files = glob.glob(f"{glob.escape(base)}.*")
        return files[0] if files else filename, info.get("title", "Music")

# دانلود و ارسال فایل صوتی یا تصویری
async def download_and_send(message, url: str, is_audio: bool):
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
        await message.edit_text(f"❌ **خطا در دریافت:** `{str(e)[:100]}`")

# ─── دستورات ───
@app.on_message(filters.me & ~filters.forwarded)
async def handle_commands(client, message):
    global TIME_NAME_ACTIVE
    if not message.text: return
    text = message.text.strip()
    chat_id = message.chat.id

    # انتخاب عدد از لیست (۱ تا ۱۰)
    clean_digit = text.translate(PERSIAN_TO_ENG)
    if clean_digit.isdigit() and message.reply_to_message and chat_id in pending_music_choices:
        idx = int(clean_digit) - 1
        res = pending_music_choices[chat_id]
        if 0 <= idx < len(res):
            url = res[idx]["url"]
            del pending_music_choices[chat_id]
            await download_and_send(message, url, True)
            return
        else:
            await message.edit_text("❌ **عدد انتخابی در لیست نیست!**")
            return

    # جستجوی هوشمند موزیک
    matched = next((p for p in MUSIC_PREFIXES if text.lower().startswith(p)), None)
    if matched:
        query = text[len(matched):].strip()
        if not query:
            await message.edit_text("❌ **لطفاً نام آهنگ یا خواننده را وارد کنید.**")
            return

        await message.edit_text(f"🔍 **در حال جستجوی دقیق برای:** `{query}`...")
        results = await asyncio.to_thread(search_yt_direct, query, 10)
        
        if not results:
            await message.edit_text("❌ **هیچ موزیکی یافت نشد!**\nلطفاً کلمات دیگری امتحان کنید.")
            return
            
        pending_music_choices[chat_id] = results
        msg = f"🎧 **نتایج ۱۰ تایی یافت شده برای:** `{query}`\n\n"
        for i, r in enumerate(results):
            msg += f"**{i+1}.** `{r['title'][:45]}`\n🎙 {r['uploader'][:25]} ⏱ `{r['duration']}`\n\n"
        
        msg += "👇 **روی همین پیام ریپلای کنید و عدد مورد نظر (مثلاً ۱ یا ۱۰) را بفرستید.**"
        await message.edit_text(msg)
        return

    # دانلود ویدیو
    elif text.lower().startswith("ویدیو ") or text.lower().startswith("کلیپ "):
        query = text.split(maxsplit=1)[1].strip()
        await message.edit_text(f"🔍 **در حال جستجوی ویدیو...**")
        results = await asyncio.to_thread(search_yt_direct, query, 1)
        if results:
            await download_and_send(message, results[0]["url"], is_audio=False)
        else:
            await message.edit_text("❌ **ویدیویی یافت نشد.**")
        return

    # دانلود مستقیم از لینک
    elif text.lower().startswith("دانلود ") or text.lower().startswith("dl "):
        query = text.split(maxsplit=1)[1].strip()
        await download_and_send(message, query, is_audio=False)
        return

    # دستورات عمومی
    elif text.lower() in ["پنل", "منو", "panel"]:
        await message.edit_text(
            "╭───「 👑 **𝗞𝗛𝗔𝗡 𝗦𝗘𝗟𝗙** 」\n"
            "├ 🎵 `اهنگ` / `موزیک` / `ترانه` <نام>\n"
            "├ 🎬 `ویدیو` / `کلیپ` <نام>\n"
            "├ ⏱ `ساعت` | `تاریخ` | `زمان`\n"
            "├ 👤 `تایم فعال` | `تایم خاموش`\n"
            "╰───「 ⚡️ 𝑂𝑛𝑙𝑖𝑛𝑒 」"
        )
    elif text.lower() == "ساعت":
        t = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
        await message.edit_text(f"⏰ ساعت: `{t}`")
    elif text == "تایم فعال":
        TIME_NAME_ACTIVE = True
        await message.edit_text("✅ اسم ساعتی فعال شد.")
    elif text == "تایم خاموش":
        TIME_NAME_ACTIVE = False
        await app.update_profile(first_name=DEFAULT_NAME)
        await message.edit_text("❌ اسم ساعتی خاموش شد.")

# تسک ساعت
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
    print("KHAN SELF ONLINE WITH DIRECT SEARCH")
    await idle()

if __name__ == "__main__":
    app.run(main())
