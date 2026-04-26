import yt_dlp
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

def progress_hook(d, msg_placeholder, loop, bot, chat_id, message_id):
    if d['status'] == 'downloading':
        p = d.get('_percent_str', '0%')
        # Telegram API limitlaridan qochish uchun har doim ham yangilamaymiz
        # Faqat muhim foizlarda yoki vaqt o'tganda yangilash kerak
        # Bu yerda oddiygina log qilamiz, main.py dagi handler buni boshqaradi
        pass

def download_video(url: str, output_path: str = "downloads", hook=None):
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{output_path}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'progress_hooks': [hook] if hook else [],
        'add_header': [
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language: en-US,en;q=0.9',
        ],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None
                
            filename = ydl.prepare_filename(info)
            
            if not os.path.exists(filename):
                base = os.path.splitext(filename)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.mov']:
                    if os.path.exists(base + ext):
                        return base + ext
            return filename
    except Exception as e:
        logger.error(f"Yuklashda xatolik: {e}")
        return None
