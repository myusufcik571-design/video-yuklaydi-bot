import asyncio
import logging
import os
import re
import time
from urllib.parse import urlparse, urlunparse

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web

import config
import database
from downloader import download_video

# Log sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot va Dispatcher
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Spamdan himoya
user_last_action = {}
RATE_LIMIT = 3 

class AdminState(StatesGroup):
    broadcasting = State()
    adding_channel_id = State()
    adding_channel_url = State()

def clean_url(url):
    parsed = urlparse(url)
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    return clean.rstrip('/')

async def check_subscription(user_id):
    channels = database.get_channels()
    if not channels:
        return True
    
    for channel in channels:
        channel_id = channel[0]
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            logger.error(f"Subscription check error for {channel_id}: {e}")
            return False
    return True

def get_sub_keyboard():
    channels = database.get_channels()
    keyboard = []
    for i, channel in enumerate(channels):
        keyboard.append([InlineKeyboardButton(text=f"Obuna bo'lish {i+1}-kanal ➕", url=channel[1])])
    keyboard.append([InlineKeyboardButton(text="Tasdiqlash ✅", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    database.add_user(message.from_user.id)
    is_subbed = await check_subscription(message.from_user.id)
    if not is_subbed:
        await message.answer("Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return
    await message.answer("Assalomu alaykum! Menga video havolasini yuboring (Instagram, TikTok, YouTube Shorts va h.k.).")

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("Rahmat! Endi video havolasini yuborishingiz mumkin.")
    else:
        await callback.answer("Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)

# Admin Panel
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id in config.ADMINS:
        kb = [
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Reklama", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_channel")],
            [InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="admin_remove_channel")],
            [InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="admin_list_channels")]
        ]
        await message.answer("Admin panel:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in config.ADMINS: return
    action = callback.data.split("_", 1)[1]
    
    if action == "stats":
        u_count = database.get_users_count()
        d_count = database.get_total_downloads()
        await callback.message.answer(f"📊 Statistika:\n\n👥 Foydalanuvchilar: {u_count}\n📥 Yuklamalar: {d_count}")
    
    elif action == "broadcast":
        await callback.message.answer("Reklama xabarini yuboring (/cancel - bekor qilish):")
        await state.set_state(AdminState.broadcasting)
        
    elif action == "add_channel":
        await callback.message.answer("Kanal ID sini yuboring (masalan, @kanal):")
        await state.set_state(AdminState.adding_channel_id)

    elif action == "remove_channel":
        channels = database.get_channels()
        if not channels: return await callback.answer("Kanallar yo'q!")
        kb = [[InlineKeyboardButton(text=c[0], callback_data=f"delchan_{c[0]}")] for c in channels]
        await callback.message.answer("O'chiriladigan kanalni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("delchan_"))
async def delchan_callback(callback: CallbackQuery):
    if callback.from_user.id in config.ADMINS:
        database.remove_channel(callback.data.split("_", 1)[1])
        await callback.answer("Kanal o'chirildi!")
        await callback.message.delete()

@dp.message(AdminState.broadcasting)
async def process_broadcast(message: Message, state: FSMContext):
    users = database.get_all_users()
    msg = await message.answer(f"Yuborilmoqda: 0/{len(users)}")
    success, blocked, failed = 0, 0, 0
    for user_id in users:
        try:
            await message.copy_to(user_id)
            success += 1
        except Exception as e:
            if "blocked" in str(e).lower(): blocked += 1
            else: failed += 1
        if (success + blocked + failed) % 50 == 0:
            try: await msg.edit_text(f"Yuborilmoqda: {success + blocked + failed}/{len(users)}")
            except: pass
    await message.answer(f"Tugatildi:\n✅ {success}\n🚫 {blocked}\n❌ {failed}")
    await state.clear()

@dp.message(AdminState.adding_channel_id)
async def process_add_channel_id(message: Message, state: FSMContext):
    await state.update_data(id=message.text)
    await message.answer("Kanal ssilkasi (havolasi)ni yuboring:")
    await state.set_state(AdminState.adding_channel_url)

@dp.message(AdminState.adding_channel_url)
async def process_add_channel_url(message: Message, state: FSMContext):
    data = await state.get_data()
    database.add_channel(data['id'], message.text)
    await message.answer("Kanal qo'shildi!")
    await state.clear()

# Video Handling
@dp.message(F.text)
async def handle_text(message: Message):
    if message.text.startswith('/'): return
    
    # Spam check
    uid = message.from_user.id
    now = time.time()
    if uid in user_last_action and now - user_last_action[uid] < RATE_LIMIT:
        return await message.answer(f"Biroz kuting ({int(RATE_LIMIT - (now-user_last_action[uid]))}s)")
    user_last_action[uid] = now

    if not await check_subscription(uid):
        return await message.answer("Avval kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())

    # Havolalarni topish (Instagram, TikTok, YouTube, Pinterest)
    url_pattern = r'(https?://(?:www\.)?(?:instagram\.com|tiktok\.com|youtube\.com|youtu\.be|pinterest\.com|pin\.it)/[^\s]+)'
    urls = re.findall(url_pattern, message.text)
    if not urls:
        return await message.answer("Iltimos, qo'llab-quvvatlanadigan havola yuboring.")

    raw_url = urls[0]
    cleaned_url = clean_url(raw_url)
    
    # Cache check
    cached = database.get_cache(cleaned_url)
    if cached:
        try:
            await message.answer_video(cached, caption="Tezkor yuklandi ⚡️")
            database.increment_downloads()
            return
        except: pass

    status_msg = await message.answer("⏳ Tayyorlanmoqda...")
    
    last_ui_update = 0
    def progress_callback(d):
        nonlocal last_ui_update
        if d['status'] == 'downloading':
            now = time.time()
            if now - last_ui_update > 3:
                percent = d.get('_percent_str', '0%')
                try:
                    asyncio.run_coroutine_threadsafe(
                        status_msg.edit_text(f"⏳ Yuklanmoqda: {percent}"),
                        asyncio.get_event_loop()
                    )
                    last_ui_update = now
                except: pass

    try:
        filepath = await asyncio.to_thread(download_video, raw_url, "downloads", progress_callback)
        if filepath and os.path.exists(filepath):
            sent = await message.answer_video(FSInputFile(filepath), caption="Bot orqali yuklandi.")
            database.add_cache(cleaned_url, sent.video.file_id)
            database.increment_downloads()
            os.remove(filepath)
        else:
            await message.answer("Xatolik: Videoni yuklab bo'lmadi. Havola noto'g'ri yoki hisob yopiq bo'lishi mumkin.")
    except Exception as e:
        logger.error(f"General handling error: {e}")
        await message.answer("Kutilmagan xatolik yuz berdi.")
    finally:
        try: await status_msg.delete()
        except: pass

# Web server for UptimeRobot
async def web_handle(request):
    return web.Response(text="Bot is online")

async def start_web():
    app = web.Application()
    app.router.add_get('/', web_handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()

async def main():
    database.create_tables()
    await start_web()
    logger.info("Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
