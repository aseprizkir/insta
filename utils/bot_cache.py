import sqlite3
import json
import time

class BotCache:
    def __init__(self, db_path="bot_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    username TEXT PRIMARY KEY,
                    data TEXT,
                    timestamp REAL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    post_url TEXT PRIMARY KEY,
                    data TEXT,
                    timestamp REAL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_cookies (
                    user_id INTEGER PRIMARY KEY,
                    cookie TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_threads_cookies (
                    user_id INTEGER PRIMARY KEY,
                    cookie TEXT,
                    lsd TEXT,
                    fb_dtsg TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_balances (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def clean_expired_cache(self):
        """Menghapus data kedaluwarsa secara permanen untuk menghemat resource server."""
        now = time.time()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Komentar kedaluwarsa setelah 3 menit (180 detik)
                cursor.execute("DELETE FROM comments WHERE ? - timestamp > 180", (now,))
                # Profil kedaluwarsa setelah 3 jam (10800 detik)
                cursor.execute("DELETE FROM profiles WHERE ? - timestamp > 10800", (now,))
                conn.commit()
        except Exception:
            pass

    def get_profile(self, username, expiry_seconds=10800):  # 3 jam
        self.clean_expired_cache()
        username = username.strip().lower().lstrip("@")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT data, timestamp FROM profiles WHERE username = ?", (username,))
                row = cursor.fetchone()
                if row:
                    data_str, timestamp = row
                    if time.time() - timestamp < expiry_seconds:
                        return json.loads(data_str)
        except Exception:
            pass
        return None

    def set_profile(self, username, data):
        username = username.strip().lower().lstrip("@")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO profiles (username, data, timestamp) VALUES (?, ?, ?)",
                    (username, json.dumps(data), time.time())
                )
                conn.commit()
        except Exception:
            pass
        self.clean_expired_cache()

    def get_comments(self, post_url, expiry_seconds=180):  # 3 menit cache
        self.clean_expired_cache()
        post_url = post_url.strip()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT data, timestamp FROM comments WHERE post_url = ?", (post_url,))
                row = cursor.fetchone()
                if row:
                    data_str, timestamp = row
                    if time.time() - timestamp < expiry_seconds:
                        return json.loads(data_str)
        except Exception:
            pass
        return None

    def set_comments(self, post_url, data):
        post_url = post_url.strip()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO comments (post_url, data, timestamp) VALUES (?, ?, ?)",
                    (post_url, json.dumps(data), time.time())
                )
                conn.commit()
        except Exception:
            pass
        self.clean_expired_cache()

    # --- User-Specific Cookies ---
    def get_user_cookie(self, user_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT cookie FROM user_cookies WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    return row[0]
        except Exception:
            pass
        return None

    def set_user_cookie(self, user_id, cookie):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO user_cookies (user_id, cookie) VALUES (?, ?)",
                    (user_id, cookie)
                )
                conn.commit()
        except Exception:
            pass

    def get_user_threads_cookie(self, user_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT cookie, lsd, fb_dtsg FROM user_threads_cookies WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    return row[0], row[1], row[2]
        except Exception:
            pass
        return None, None, None

    def set_user_threads_cookie(self, user_id, cookie, lsd="", fb_dtsg=""):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO user_threads_cookies (user_id, cookie, lsd, fb_dtsg) VALUES (?, ?, ?, ?)",
                    (user_id, cookie, lsd, fb_dtsg)
                )
                conn.commit()
        except Exception:
            pass

    # --- Billing & Balances ---
    def get_balance(self, user_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT balance FROM user_balances WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    return row[0]
        except Exception:
            pass
        return 0

    def add_balance(self, user_id, amount):
        current = self.get_balance(user_id)
        new_balance = current + amount
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO user_balances (user_id, balance) VALUES (?, ?)",
                    (user_id, new_balance)
                )
                conn.commit()
            return new_balance
        except Exception:
            return current

    def deduct_balance(self, user_id, amount=1000):
        current = self.get_balance(user_id)
        if current < amount:
            return False
        new_balance = current - amount
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO user_balances (user_id, balance) VALUES (?, ?)",
                    (user_id, new_balance)
                )
                conn.commit()
            return True
        except Exception:
            return False

    # --- Admin Dashboard Stats ---
    def get_stats(self):
        """Mengambil data statistik dasar untuk admin panel."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Hitung total pengguna terdaftar
                cursor.execute("SELECT COUNT(*) FROM user_balances")
                total_users = cursor.fetchone()[0]
                
                # Hitung total saldo yang beredar
                cursor.execute("SELECT SUM(balance) FROM user_balances")
                total_balances = cursor.fetchone()[0] or 0
                
                # Hitung total postingan komentar yang ter-cache
                cursor.execute("SELECT COUNT(*) FROM comments")
                total_comments = cursor.fetchone()[0]
                
                return total_users, total_balances, total_comments
        except Exception:
            return 0, 0, 0

    def clear_all_cache(self):
        """Menghapus seluruh cache (profiles & comments) secara paksa."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM comments")
                cursor.execute("DELETE FROM profiles")
                conn.commit()
            return True
        except Exception:
            return False
