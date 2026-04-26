import asyncio
import logging
import os
import re
from urllib.parse import urlparse, urlunparse
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import config
import database
from downloader import download_video
import time

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# States
class AdminState(StatesGroup):
    broadcasting = State()
    adding_channel_id = State()
    adding_channel_url = State()
    removing_channel = State()

def clean_url(url):
    parsed = urlparse(url)
    # Ba'zi parametrlarni tozalaymiz, masalan ?igsh= yoki ?utm_source=
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    # oxiridagi slashlarni olib tashlaymiz
    return clean.rstrip('/')

# Middleware / Utility func for channel check
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
            logging.error(f"Error checking sub for {channel_id}: {e}")
            # Agar bot kanalda admin bo'lmasa yoki kanal topilmasa, obuna bo'lmagan deb hisoblaymiz
            return False
    return True

def get_sub_keyboard():
    channels = database.get_channels()
    keyboard = []
    for i, channel in enumerate(channels):
        channel_url = channel[1]
        keyboard.append([InlineKeyboardButton(text=f"Obuna bo'lish {i+1}-kanal ➕", url=channel_url)])
    keyboard.append([InlineKeyboardButton(text="Tasdiqlash ✅", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    database.add_user(message.from_user.id)
    
    is_subbed = await check_subscription(message.from_user.id)
    if not is_subbed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz kerak:",
            reply_markup=get_sub_keyboard()
        )
        return

    await message.answer("Assalomu alaykum! Menga Instagram videosining ssilkasini yuboring. Men uni tezda yuklab beraman.")

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    is_subbed = await check_subscription(callback.from_user.id)
    if not is_subbed:
        await callback.answer("Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        await callback.message.delete()
        await callback.message.answer("Rahmat! Endi menga Instagram videosining ssilkasini yuboring.")

# Admin Panel
def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Xabar yuborish (Reklama)", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="➕ Majburiy kanal qo'shish", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="➖ Majburiy kanal o'chirish", callback_data="admin_remove_channel")],
        [InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="admin_list_channels")]
    ])

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id in config.ADMINS:
        await message.answer("Admin panelga xush kelibsiz:", reply_markup=get_admin_keyboard())

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in config.ADMINS:
        return
    
    action = callback.data.split("_", 1)[1]
    
    if action == "stats":
        user_count = database.get_users_count()
        download_count = database.get_total_downloads()
        await callback.message.answer(
            f"📊 Bot statistikasi:\n\n"
            f"👥 Jami foydalanuvchilar: {user_count} ta\n"
            f"📥 Jami yuklamalar: {download_count} ta",
            show_alert=True
        )
        
    elif action == "broadcast":
        await callback.message.answer("Foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing yoki forward qiling (bekor qilish uchun /cancel yozing):")
        await state.set_state(AdminState.broadcasting)
        
    elif action == "add_channel":
        await callback.message.answer("Qo'shiladigan kanal ID sini yoki username sini yozing (masalan, -100123456789 yoki @kanal_user):\n\nBot ushbu kanalda admin bo'lishi shart!")
        await state.set_state(AdminState.adding_channel_id)
        
    elif action == "remove_channel":
        channels = database.get_channels()
        if not channels:
            await callback.answer("Majburiy kanallar yo'q!", show_alert=True)
            return
        
        kb = []
        for c in channels:
            kb.append([InlineKeyboardButton(text=c[0], callback_data=f"delchan_{c[0]}")])
        await callback.message.answer("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        
    elif action == "list_channels":
        channels = database.get_channels()
        if not channels:
            await callback.answer("Majburiy kanallar yo'q!", show_alert=True)
            return
        
        text = "Majburiy kanallar ro'yxati:\n\n"
        for i, c in enumerate(channels):
            text += f"{i+1}. ID: {c[0]}\nSsilka: {c[1]}\n\n"
        await callback.message.answer(text, disable_web_page_preview=True)

@dp.callback_query(F.data.startswith("delchan_"))
async def delchan_callback(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMINS:
        return
    channel_id = callback.data.split("_", 1)[1]
    database.remove_channel(channel_id)
    await callback.answer("Kanal muvaffaqiyatli o'chirildi!", show_alert=True)
    await callback.message.delete()

@dp.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext):
    if message.from_user.id in config.ADMINS:
        await state.clear()
        await message.answer("Amal bekor qilindi.")

@dp.message(AdminState.broadcasting)
async def process_broadcast(message: Message, state: FSMContext):
    users = database.get_all_users()
    total = len(users)
    await message.answer(f"Xabar {total} ta foydalanuvchiga yuborilmoqda, kuting...")
    
    success = 0
    blocked = 0
    failed = 0
    
    for user_id in users:
        try:
            await message.copy_to(chat_id=user_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            if "bot was blocked by the user" in str(e).lower():
                blocked += 1
            else:
                failed += 1
    
    await message.answer(
        f"📢 Reklama yuborish yakunlandi:\n\n"
        f"✅ Muvaffaqiyatli: {success}\n"
        f"🚫 Bloklaganlar: {blocked}\n"
        f"❌ Xatolik: {failed}\n"
        f"👥 Jami: {total}"
    )
    await state.clear()

@dp.message(AdminState.adding_channel_id)
async def process_add_channel_id(message: Message, state: FSMContext):
    await state.update_data(channel_id=message.text)
    await message.answer("Ajoyib, endi foydalanuvchilar ulanishi uchun ushbu kanalning taklif ssilkasini yozing (masalan, https://t.me/kanal_user):")
    await state.set_state(AdminState.adding_channel_url)

@dp.message(AdminState.adding_channel_url)
async def process_add_channel_url(message: Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data['channel_id']
    url = message.text
    database.add_channel(channel_id, url)
    await message.answer(f"Kanal muvaffaqiyatli qo'shildi!\nID: {channel_id}\nSsilka: {url}")
    await state.clear()

# Instagram handling
@dp.message(F.text)
async def handle_text(message: Message):
    if message.from_user.id in config.ADMINS and message.text.startswith('/'):
        return

    database.add_user(message.from_user.id)
    
    is_subbed = await check_subscription(message.from_user.id)
    if not is_subbed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz kerak:",
            reply_markup=get_sub_keyboard()
        )
        return
    
    text = message.text
    if "instagram.com" in text:
        # URL ni ajratib olish
        urls = re.findall(r'(https?://(?:www\.)?instagram\.com/[^\s]+)', text)
        if not urls:
            return
        
        raw_url = urls[0]
        cleaned_url = clean_url(raw_url)
        
        # Keshlangan videoni tekshirish (Tezkor yuklash uchun)
        cached_file_id = database.get_cache(cleaned_url)
        if cached_file_id:
            try:
                await message.answer_video(video=cached_file_id, caption="Tezkor yuklandi⚡️")
                database.increment_downloads()
                return
            except Exception as e:
                logging.error(f"Keshdan yuborishda xatolik: {e}")
                # Agar file_id yaroqsiz bo'lib qolgan bo'lsa, qayta yuklaymiz.
                pass
        
        msg = await message.answer("⏳ Video yuklanmoqda, kuting...")
        
        # Progress bar uchun maxsus hook funksiyasi
        last_update = 0
        def my_hook(d):
            nonlocal last_update
            if d['status'] == 'downloading':
                current_time = time.time()
                if current_time - last_update > 2: # Har 2 soniyada yangilash
                    p = d.get('_percent_str', '0%')
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    asyncio.run_coroutine_threadsafe(
                        msg.edit_text(f"⏳ Yuklanmoqda: {p}\n🚀 Tezlik: {speed}\n🏁 Qoldi: {eta}"),
                        asyncio.get_event_loop()
                    )
                    last_update = current_time

        # Videoni yuklab olish (Non-blocking)
        try:
            # yt-dlp ni alohida thread da yurgizamiz
            filepath = await asyncio.to_thread(download_video, raw_url, "downloads", my_hook)
            
            if filepath and os.path.exists(filepath):
                # Videoni yuborish
                video = FSInputFile(filepath)
                sent_msg = await message.answer_video(video=video, caption="Bot orqali yuklab olindi.")
                
                # File ID ni keshga saqlash
                database.add_cache(cleaned_url, sent_msg.video.file_id)
                database.increment_downloads()
                
                # Local faylni tozalash
                try:
                    os.remove(filepath)
                except:
                    pass
            else:
                await message.answer("Kechirasiz, videoni yuklab olishning iloji bo'lmadi. Havolani tekshirib qaytadan urinib ko'ring yoki hisob yopiq (private) bo'lishi mumkin.")
        except Exception as e:
            logging.error(f"Download error: {e}")
            await message.answer("Xatolik yuz berdi. Iltimos keyinroq qayta urinib ko'ring.")
            
        await msg.delete()
    else:
        await message.answer("Iltimos, menga faqat Instagram videosi havolasini yuboring.")

# Web server for UptimeRobot
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("Web server started on port 8080...")

async def main():
    database.create_tables()
    # Web serverni ishga tushirish (UptimeRobot uchun)
    await start_web_server()
    # Bot ishga tushganligi haqida xabar berish (ixtiyoriy)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
