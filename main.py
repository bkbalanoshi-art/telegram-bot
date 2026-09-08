from pyrogram import Client, filters
import os
import asyncio

api_id = int(os.environ["API_ID"])
api_hash = os.environ["API_HASH"]
session_string = os.environ["SESSION_STRING"]

app = Client(
    name="my_account",
    api_id=api_id,
    api_hash=api_hash,
    session_string=session_string
)

REPLIES = {
    "سلام": "سلام! من سلف باتم 🤖",
    "خوبی": "ممنون، تو چوبی؟",
    "ربات": "بله، من یه ربات خودکارم",
    "کمک": "دستورات: سلام، خوبی، ربات، ساعت، کمک",
    "ساعت": "ساعت الان رو نمیدونم ولی فعالم!",
}

@app.on_message(filters.private)
async def handle_message(client, message):
    try:
        if message.from_user and message.from_user.is_self:
            return

        if not message.text:
            return

        text = message.text
        for key, reply in REPLIES.items():
            if key in text:
                await message.reply(reply)
                return

    except Exception as e:
        print(f"Error: {e}")

async def main():
    await app.start()
    me = await app.get_me()
    print("=" * 50)
    print("✅ ربات راه افتاد!")
    print(f"اکانت: {me.first_name}")
    print("=" * 50)
    await asyncio.sleep(99999999)

if __name__ == "__main__":
    app.run(main())
