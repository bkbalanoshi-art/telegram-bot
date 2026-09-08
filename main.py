import asyncio
import glob
import os
import re
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

# تنظیمات زمانی و حافظه موقت
IRAN_TZ = ZoneInfo("Asia/Tehran")
DEFAULT_NAME = "𝗞𝗛𝗔𝗡"
TIME_NAME_ACTIVE = False
pending_music_choices = {}

# تبدیل اعداد فارسی به انگلیسی
PERSIAN_TO_ENG = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
BOLD_DIGITS = {"0": "𝟎", "1": "𝟏", "2": "𝟐", "3": "𝟑", "4": "𝟒", "5": "𝟓", "6": "𝟔", "7": "𝟕", "8": "𝟖", "9": "𝟗", ":": ":"}

def to_bold_time(t): 
    return "".join(BOLD_DIGITS.get(c, c) for c in t)

MUSIC_PREFIXES = (
    "اهنگ ", "آهنگ ", "موزیک ", "ترانه ", "ریمیکس ", "رمیکس ",
    "دانلود اهنگ ", "دانلود آهنگ ", "دانلود موزیک ", "صوتی "
)

# ─── موتور جستجوی هوشمند بدون نیاز به API واسطه ───
def search_music_ultra(query: str, max_results=10):
    os.makedirs("downloads", exist_ok=True)
    
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android", "mweb"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15"
        }
    }

    results = []
    seen_urls = set()

    # اولویت جستجو: ۱. یوتیوب موزیک | ۲. یوتیوب عمومی
    search_queries = [
        f"ytmusicsearch{max_results}:{query}",
        f"ytsearch{max_results}:{query}"
    ]

    for sq in search_queries:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(sq, download=False)
                if info and "entries" in info:
                    for entry in info["entries"]:
                        if not entry:
                            continue
                        
                        url = entry.get("url") or entry.get("webpage_url")
                        if not url and entry.get("id"):
                            url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                        
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            dur = int(entry.get("duration") or 0)
                            results.append({
                                "title": entry.get("title", "Music"),
                                "url": url,
                                "duration": dur,
                                "uploader": entry.get("uploader") or entry.get("channel") or "Artist"
                            })
                            
                        if len(results) >= max_results:
                            break
        except Exception as e:
            print(f"Search Error ({sq}): {e}")
            continue

        if len(results) >= max_results:
            break

    return results[:max_results]

# ─── دانلودر قدرتمند ───
def run_yt_download(url: str, is_audio: bool):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android", "mweb"]
            }
        },
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
            "format": "best[ext=mp4]/best"
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if is_audio:
            base = os.path.splitext(filename)[0]
            files = glob.glob(f"{glob.escape(base)}.*")
            filename = files[0] if files else base + ".mp3"
        return filename, info.get("title", "Music")

# ─── پردازش دستورات ───
@app.on_message(filters.me & ~filters.forwarded)
async def main_handler(client, message):
    global TIME_NAME_ACTIVE
    if not message.text: 
        return
    
    text = message.text.strip()
    lower_text = text.lower()
    chat_id = message.chat.id

    # تبدیل اعداد فارسی به انگلیسی
    clean_text = text.translate(PERSIAN_TO_ENG)

    # ۱. انتخاب عدد از لیست (ریپلای)
    if clean_text.isdigit() and message.reply_to_message and chat_id in pending_music_choices:
        idx = int(clean_text) - 1
        res_list = pending_music_choices[chat_id]
        if 0 <= idx < len(res_list):
            target_url = res_list[idx]["url"]
            del pending_music_choices[chat_id]
            
            await message.edit_text("⏳ **در حال دانلود با بالاترین کیفیت...**")
            try:
                path, title = await asyncio.to_thread(run_yt_download, target_url, True)
                await message.edit_text("📤 **در حال آپلود به تلگرام...**")
                await message.reply_audio(path, caption=f"🎵 **{title}**")
                await message.delete()
                if os.path.exists(path): 
                    os.remove(path)
            except Exception as e:
                await message.edit_text(f"❌ **خطا در دانلود:** `{str(e)[:150]}`")
        else:
            await message.edit_text("❌ **عدد انتخابی در لیست نیست!**")
        return

    # ۲. جستجوی آهنگ
    matched_prefix = next((p for p in MUSIC_PREFIXES if lower_text.startswith(p)), None)
    if matched_prefix:
        query = text[len(matched_prefix):].strip()
        if not query:
            await message.edit_text("❌ **لطفاً نام آهنگ یا خواننده را وارد کنید.**")
            return

        await message.edit_text(f"🔍 **در حال جستجوی دقیق برای:** `{query}`...")
        
        results = await asyncio.to_thread(search_music_ultra, query, 10)
        
        if not results:
            await message.edit_text("❌ **هیچ موزیکی پیدا نشد!**\nلطفاً کلمات دیگری را امتحان کنید.")
            return

        pending_music_choices[chat_id] = results
        
        msg = f"🎧 **نتایج ۱۰ تایی برای:** `{query}`\n\n"
        for i, r in enumerate(results):
            dur = f"{r['duration']//60}:{r['duration']%60:02d}" if r['duration'] else "??:??"
            msg += f"**{i+1}.** `{r['title'][:42]}` | `{dur}`\n"
            
        msg += "\n👇 **روی همین پیام ریپلای کنید و عدد مورد نظر (مثلاً ۱ یا ۱۰) را بفرستید.**"
        await message.edit_text(msg)
        return

    # ۳. دانلود ویدیو
    elif lower_text.startswith("ویدیو ") or lower_text.startswith("کلیپ "):
        query = text.split(maxsplit=1)[1].strip()
        await message.edit_text(f"🔍 **در حال جستجوی ویدیو...**")
        results = await asyncio.to_thread(search_music_ultra, query, 1)
        if results:
            try:
                path, title = await asyncio.to_thread(run_yt_download, results[0]["url"], False)
                await message.reply_video(path, caption=f"🎬 **{title}**")
                await message.delete()
                if os.path.exists(path): os.remove(path)
            except Exception as e:
                await message.edit_text(f"❌ **خطا:** `{str(e)[:100]}`")
        else:
            await message.edit_text("❌ **ویدیویی یافت نشد.**")
        return

    # ۴. دستورات عمومی
    elif lower_text in ["پنل", "منو", "panel"]:
        await message.edit_text(
            "╭───「 👑 **𝗞𝗛𝗔𝗡 𝗦𝗘𝗟𝗙** 」\n"
            "│\n"
            "├ 🎵 `اهنگ <نام>` ➔ جستجوی لیست ۱۰ تایی\n"
            "├ 🎬 `ویدیو <نام>` ➔ دانلود ویدیو\n"
            "├ ⏱ `ساعت` | `زمان` ➔ نمایش زمان\n"
            "├ 👤 `تایم فعال` | `تایم خاموش` ➔ اسم ساعتی\n"
            "│\n"
            "╰───「 ⚡️ 𝑂𝑛𝑙𝑖𝑛𝑒 」"
        )
    elif lower_text == "ساعت":
        t = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
        await message.edit_text(f"⏰ ساعت ایران: `{t}`")
    elif lower_text == "پینگ":
        await message.edit_text("🚀 **سلف‌بات فعال و آنلاین است!**")
    elif text == "تایم فعال":
        TIME_NAME_ACTIVE = True
        await message.edit_text("✅ **اسم ساعتی فعال شد.**")
    elif text == "تایم خاموش":
        TIME_NAME_ACTIVE = False
        await app.update_profile(first_name=DEFAULT_NAME)
        await message.edit_text("❌ **اسم ساعتی خاموش شد.**")

# ─── تسک پس‌زمینه اسم ساعتی ───
async def time_task():
    while True:
        if TIME_NAME_ACTIVE:
            try:
                now = datetime.now(IRAN_TZ).strftime("%H:%M")
                bold = to_bold_time(now)
                await app.update_profile(first_name=f"{DEFAULT_NAME} ┃ {bold}")
            except: 
                pass
        await asyncio.sleep(60)

async def main():
    await app.start()
    asyncio.create_task(time_task())
    print("KHAN SELF IS ONLINE & READY")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
