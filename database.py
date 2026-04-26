import sqlite3

def create_connection():
    conn = sqlite3.connect('bot.db')
    return conn

def create_tables():
    conn = create_connection()
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
    
    # Boshlang'ich qiymatni o'rnatish
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('total_downloads', '0')")
    
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def get_users_count():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

def add_cache(url, file_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO cache (url, file_id) VALUES (?, ?)', (url, file_id))
    conn.commit()
    conn.close()

def get_cache(url):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT file_id FROM cache WHERE url = ?', (url,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return None

def add_channel(channel_id, url):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO channels (channel_id, url) VALUES (?, ?)', (channel_id, url))
    conn.commit()
    conn.close()

def remove_channel(channel_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
    conn.commit()
    conn.close()

def get_channels():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT channel_id, url FROM channels')
    channels = cursor.fetchall()
    conn.close()
    return channels

def increment_downloads():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) WHERE key = 'total_downloads'")
    conn.commit()
    conn.close()

def get_total_downloads():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'total_downloads'")
    result = cursor.fetchone()
    conn.close()
    if result:
        return int(result[0])
    return 0

if __name__ == '__main__':
    create_tables()
