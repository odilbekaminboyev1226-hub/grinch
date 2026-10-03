import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google import genai

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ai_client = genai.Client(api_key=GEMINI_API_KEY)
scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

pending_posts = {}

async def generate_ai_content() -> str:
    try:
        response = await asyncio.to_thread(
            ai_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=(
                "Siz Telegram kanal uchun professional kontent-menjersiz. "
                "Jozibali, o'qilishi oson, emojilar bilan boyitilgan va auditoriyani "
                "qiziqtiradigan qisqa post yozib bering. O'zbek tilida javob bering."
            )
        )
        return response.text
    except Exception as e:
        logging.error(f"Gemini API error: {e}")
        return "⚠️ Post generatsiya qilishda xatolik yuz berdi."

async def trigger_scheduled_post():
    if not ADMIN_ID:
        return

    content = await generate_ai_content()
    post_id = int(datetime.now().timestamp())
    pending_posts[post_id] = content

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash va Joylash", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton(text="🔄 Qayta generatsiya", callback_data=f"regenerate_{post_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{post_id}")
        ]
    ])

    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🤖 **AI tomonidan tayyorlangan yangi post:**\n\n{content}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text == "/test")
async def test_handler(message: types.Message):
    await message.answer("🧪 Post generatsiya qilinmoqda, kuting...")
    await trigger_scheduled_post()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_post(callback: types.CallbackQuery):
    post_id = int(callback.data.split("_")[1])
    content = pending_posts.get(post_id)

    if content:
        await bot.send_message(chat_id=CHANNEL_ID, text=content)
        await callback.message.edit_text(f"✅ **Kanalga joylandi!**\n\n{content}")
        del pending_posts[post_id]

@dp.callback_query(F.data.startswith("regenerate_"))
async def regenerate_post(callback: types.CallbackQuery):
    await callback.answer("Yangi post tayyorlanmoqda...")
    new_content = await generate_ai_content()
    post_id = int(callback.data.split("_")[1])
    pending_posts[post_id] = new_content

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash va Joylash", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton(text="🔄 Qayta generatsiya", callback_data=f"regenerate_{post_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{post_id}")
        ]
    ])

    await callback.message.edit_text(
        text=f"🤖 **Yangi qayta generatsiya qilingan post:**\n\n{new_content}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("reject_"))
async def reject_post(callback: types.CallbackQuery):
    post_id = int(callback.data.split("_")[1])
    if post_id in pending_posts:
        del pending_posts[post_id]
    await callback.message.edit_text("❌ **Post bekor qilindi.**")

async def main():
    scheduler.add_job(trigger_scheduled_post, 'cron', hour=4, minute=20)
    scheduler.add_job(trigger_scheduled_post, 'cron', hour=13, minute=35)
    scheduler.add_job(trigger_scheduled_post, 'cron', hour=20, minute=50)

    scheduler.start()
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
