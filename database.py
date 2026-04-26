import sqlite3
import os

# Ma'lumotlar bazasi yo'li (dinamik va xavfsiz)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bot.db')

def create_connection():
    return sqlite3.connect(DB_PATH)

def create_tables():
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                url TEXT PRIMARY KEY,
                file_id TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                url TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('total_downloads', '0')")
        conn.commit()

def add_user(user_id):
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()

def get_users_count():
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]

def get_all_users():
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        return [user[0] for user in cursor.fetchall()]

def add_cache(url, file_id):
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO cache (url, file_id) VALUES (?, ?)', (url, file_id))
        conn.commit()

def get_cache(url):
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT file_id FROM cache WHERE url = ?', (url,))
        result = cursor.fetchone()
        return result[0] if result else None

def add_channel(channel_id, url):
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO channels (channel_id, url) VALUES (?, ?)', (channel_id, url))
        conn.commit()

def remove_channel(channel_id):
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
        conn.commit()

def get_channels():
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT channel_id, url FROM channels')
        return cursor.fetchall()

def increment_downloads():
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) WHERE key = 'total_downloads'")
        conn.commit()

def get_total_downloads():
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'total_downloads'")
        result = cursor.fetchone()
        return int(result[0]) if result else 0
