import asyncio
import glob
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import static_ffmpeg
import yt_dlp

# ─── 🛠 رفع قطعی باگ Peer ID برای آیدی‌های جدید تلگرام (-1003...) ───
import pyrogram.utils

pyrogram.utils.MIN_CHANNEL_ID = -100999999999999
pyrogram.utils.MIN_CHAT_ID = -99999999999999

def custom_get_peer_type(peer_id: int) -> str:
    if isinstance(peer_id, int):
        if peer_id < 0:
            if str(peer_id).startswith("-100"):
                return "channel"
            return "chat"
        elif peer_id > 0:
            return "user"
    raise ValueError(f"Peer id invalid: {peer_id}")

pyrogram.utils.get_peer_type = custom_get_peer_type
# ───────────────────────────────────────────────────────────────────

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
    "دانلود اهنگ ", "دانلود آهنگ ", "دانلود موزیک ", "دانلود ترانه ",
    "دانلود ریمیکس ", "اهنگ جدید ", "آهنگ جدید ", "صوتی "
)

async def safe_edit(client, message, text):
    try:
        await message.edit_text(text)
    except Exception:
        try:
            await client.send_message(message.chat.id, text)
            try:
                await message.delete()
            except Exception:
                pass
        except Exception as e:
            print(f"Safe Edit Error: {e}")

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

@app.on_message(filters.me & ~filters.forwarded)
async def main_handler(client, message):
    global TIME_NAME_ACTIVE
    if not message or not message.text: 
        return
    
    text = message.text.strip()
    lower_text = text.lower()
    chat_id = message.chat.id

    clean_text = text.translate(PERSIAN_TO_ENG)

    # ۱. انتخاب عدد از لیست ۱۰ تایی (ریپلای)
    if clean_text.isdigit() and message.reply_to_message and chat_id in pending_music_choices:
        idx = int(clean_text) - 1
        res_list = pending_music_choices[chat_id]
        if 0 <= idx < len(res_list):
            target_url = res_list[idx]["url"]
            del pending_music_choices[chat_id]
            
            await safe_edit(client, message, "⏳ **در حال دانلود با بالاترین کیفیت...**")
            try:
                path, title = await asyncio.to_thread(run_yt_download, target_url, True)
                await safe_edit(client, message, "📤 **در حال آپلود به تلگرام...**")
                await message.reply_audio(path, caption=f"🎵 **{title}**")
                try:
                    await message.delete()
                except Exception:
                    pass
                if os.path.exists(path): 
                    os.remove(path)
            except Exception as e:
                await safe_edit(client, message, f"❌ **خطا در دانلود:** `{str(e)[:150]}`")
        else:
            await safe_edit(client, message, "❌ **عدد انتخابی در لیست نیست!**")
        return

    # ۲. جستجوی آهنگ
    matched_prefix = next((p for p in MUSIC_PREFIXES if lower_text.startswith(p)), None)
    if matched_prefix:
        query = text[len(matched_prefix):].strip()
        if not query:
            await safe_edit(client, message, "❌ **لطفاً نام آهنگ یا خواننده را وارد کنید.**")
            return

        await safe_edit(client, message, f"🔍 **در حال جستجوی دقیق برای:** `{query}`...")
        
        results = await asyncio.to_thread(search_music_ultra, query, 10)
        
        if not results:
            await safe_edit(client, message, "❌ **هیچ موزیکی پیدا نشد!**\nلطفاً کلمات دیگری را امتحان کنید.")
            return

        pending_music_choices[chat_id] = results
        
        msg = f"🎧 **نتایج ۱۰ تایی برای:** `{query}`\n\n"
        for i, r in enumerate(results):
            dur = f"{r['duration']//60}:{r['duration']%60:02d}" if r['duration'] else "??:??"
            msg += f"**{i+1}.** `{r['title'][:42]}` | `{dur}`\n"
            
        msg += "\n👇 **روی همین پیام ریپلای کنید و عدد مورد نظر (مثلاً ۱ یا ۱۰) را بفرستید.**"
        await safe_edit(client, message, msg)
        return

    # ۳. دانلود ویدیو
    elif lower_text.startswith("ویدیو ") or lower_text.startswith("کلیپ "):
        query = text.split(maxsplit=1)[1].strip()
        await safe_edit(client, message, f"🔍 **در حال جستجوی ویدیو...**")
        results = await asyncio.to_thread(search_music_ultra, query, 1)
        if results:
            try:
                path, title = await asyncio.to_thread(run_yt_download, results[0]["url"], False)
                await message.reply_video(path, caption=f"🎬 **{title}**")
                try:
                    await message.delete()
                except Exception:
                    pass
                if os.path.exists(path): os.remove(path)
            except Exception as e:
                await safe_edit(client, message, f"❌ **خطا:** `{str(e)[:100]}`")
        else:
            await safe_edit(client, message, "❌ **ویدیویی یافت نشد.**")
        return

    # ۴. دستورات عمومی
    elif lower_text in ["پنل", "منو", "panel"]:
        await safe_edit(client, message, 
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
        await safe_edit(client, message, f"⏰ ساعت ایران: `{t}`")
    elif lower_text == "پینگ":
        await safe_edit(client, message, "🚀 **سلف‌بات فعال و آنلاین است!**")
    elif text == "تایم فعال":
        TIME_NAME_ACTIVE = True
        await safe_edit(client, message, "✅ **اسم ساعتی فعال شد.**")
    elif text == "تایم خاموش":
        TIME_NAME_ACTIVE = False
        await app.update_profile(first_name=DEFAULT_NAME)
        await safe_edit(client, message, "❌ **اسم ساعتی خاموش شد.**")

async def time_task():
    while True:
        if TIME_NAME_ACTIVE:
            try:
                now = datetime.now(IRAN_TZ).strftime("%H:%M")
                bold = to_bold_time(now)
                await app.update_profile(first_name=f"{DEFAULT_NAME} ┃ {bold}")
            except Exception: 
                pass
        await asyncio.sleep(60)

async def main():
    await app.start()
    asyncio.create_task(time_task())
    print("KHAN SELF IS ONLINE & READY")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
