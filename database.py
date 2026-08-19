import aiosqlite
import asyncio

DB_PATH = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                plan TEXT NOT NULL,
                price INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                screenshot_file_id TEXT,
                xui_client_id TEXT,
                xui_email TEXT,
                gift_to_user_id INTEGER,
                gift_to_username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                authenticated INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                referrer_id INTEGER,
                partner_referrer_id INTEGER,
                referral_count INTEGER DEFAULT 0,
                bonus_days INTEGER DEFAULT 0,
                trial_used INTEGER DEFAULT 0,
                partner_link TEXT,
                partner_earnings INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                bonus_given INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Миграции на случай существующей БД
        for col, col_type in [
            ("gift_to_user_id", "INTEGER"),
            ("gift_to_username", "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE orders ADD COLUMN {col} {col_type}")
            except Exception:
                pass

        for col, col_type in [
            ("referrer_id", "INTEGER"),
            ("partner_referrer_id", "INTEGER"),
            ("referral_count", "INTEGER DEFAULT 0"),
            ("bonus_days", "INTEGER DEFAULT 0"),
            ("trial_used", "INTEGER DEFAULT 0"),
            ("partner_link", "TEXT"),
            ("partner_earnings", "INTEGER DEFAULT 0"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            except Exception:
                pass

        await db.commit()
    await init_prices()


async def init_prices():
    """Записать цены из config в БД, если они ещё не заданы."""
    import config
    defaults = {
        "price_1_month": config.PRICE_1_MONTH,
        "price_3_months": config.PRICE_3_MONTHS,
        "price_6_months": config.PRICE_6_MONTHS,
        "price_12_months": config.PRICE_12_MONTHS,
    }
    async with aiosqlite.connect(DB_PATH) as db:
        for key, value in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )
        await db.commit()


async def get_prices() -> dict:
    """Вернуть актуальные цены из БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT key, value FROM settings WHERE key LIKE 'price_%'"
        )
        rows = await cursor.fetchall()
    return {row[0]: int(row[1]) for row in rows}


async def set_price(plan_key: str, price: int):
    """Обновить цену тарифа (plan_key: price_1_month и т.д.)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (plan_key, str(price))
        )
        await db.commit()


# ── Orders ────────────────────────────────────────────────────────────────────

async def create_order(user_id, username, full_name, plan, price,
                       gift_to_user_id=None, gift_to_username=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO orders (user_id, username, full_name, plan, price,
               gift_to_user_id, gift_to_username) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, full_name, plan, price,
             gift_to_user_id, gift_to_username)
        )
        await db.commit()
        return cursor.lastrowid


async def update_order_screenshot(order_id, file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET screenshot_file_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (file_id, order_id)
        )
        await db.commit()


async def get_order(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        return await cursor.fetchone()


async def update_order_status(order_id, status, xui_client_id=None, xui_email=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE orders SET status=?, xui_client_id=?, xui_email=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (status, xui_client_id, xui_email, order_id)
        )
        await db.commit()


async def get_pending_orders():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE status='pending' ORDER BY created_at DESC"
        )
        return await cursor.fetchall()


async def get_user_orders(user_id: int) -> list:
    """История заказов пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
            (user_id,)
        )
        return await cursor.fetchall()


async def get_active_vpn(user_id: int):
    """Получить последний одобренный заказ (активный VPN)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM orders
               WHERE user_id=? AND status='approved'
               ORDER BY updated_at DESC LIMIT 1""",
            (user_id,)
        )
        return await cursor.fetchone()


# ── Users & Profile ───────────────────────────────────────────────────────────

async def get_or_create_user(user_id: int, username: str = "", full_name: str = "") -> dict:
    """Получить или создать профиль пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
        if row:
            await db.execute(
                "UPDATE users SET username=?, full_name=? WHERE user_id=?",
                (username or row["username"], full_name or row["full_name"], user_id)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            return await cursor.fetchone()
        else:
            await db.execute(
                """INSERT INTO users (user_id, username, full_name)
                   VALUES (?, ?, ?)""",
                (user_id, username, full_name)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            return await cursor.fetchone()


async def get_user_profile(user_id: int):
    """Получить профиль пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cursor.fetchone()


async def set_referrer(user_id: int, referrer_id: int, is_partner: bool = False) -> bool:
    """Привязать реферера. Возвращает True если реферер установлен впервые."""
    if user_id == referrer_id:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT referrer_id, partner_referrer_id FROM users WHERE user_id=?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False

        col = "partner_referrer_id" if is_partner else "referrer_id"
        if row[col] is not None:
            return False  # уже привязан

        await db.execute(
            f"UPDATE users SET {col}=? WHERE user_id=?",
            (referrer_id, user_id)
        )
        await db.commit()
        return True


async def add_referral_bonus(referrer_id: int, referred_id: int, bonus_days: int) -> bool:
    """Начислить бонусные дни за приглашение друга (+bonus_days обоим)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id FROM referrals WHERE referrer_id=? AND referred_id=?",
            (referrer_id, referred_id)
        )
        if await cursor.fetchone():
            return False

        await db.execute(
            "INSERT INTO referrals (referrer_id, referred_id, bonus_given) VALUES (?, ?, 1)",
            (referrer_id, referred_id)
        )
        await db.execute(
            "UPDATE users SET referral_count = referral_count + 1, bonus_days = bonus_days + ? WHERE user_id=?",
            (bonus_days, referrer_id)
        )
        await db.execute(
            "UPDATE users SET bonus_days = bonus_days + ? WHERE user_id=?",
            (bonus_days, referred_id)
        )
        await db.commit()
        return True


async def use_bonus_days(user_id: int) -> int:
    """Списать все бонусные дни и вернуть количество списанных дней."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT bonus_days FROM users WHERE user_id=?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row or row[0] <= 0:
            return 0
        days = row[0]
        await db.execute(
            "UPDATE users SET bonus_days = 0 WHERE user_id=?", (user_id,)
        )
        await db.commit()
        return days


async def use_trial(user_id: int) -> bool:
    """Использовать пробный день. Возвращает True если пробный день успешно активирован."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT trial_used FROM users WHERE user_id=?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row or row[0] == 1:
            return False
        await db.execute(
            "UPDATE users SET trial_used=1 WHERE user_id=?", (user_id,)
        )
        await db.commit()
        return True


async def set_partner_link(user_id: int, link: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET partner_link=? WHERE user_id=?",
            (link, user_id)
        )
        await db.commit()


async def add_partner_earnings(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET partner_earnings = partner_earnings + ? WHERE user_id=?",
            (amount, user_id)
        )
        await db.commit()


async def find_user_by_username(username: str):
    """Найти пользователя по username."""
    clean_username = username.lstrip("@").strip()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE LOWER(username)=LOWER(?)", (clean_username,)
        )
        return await cursor.fetchone()


# ── Admins ────────────────────────────────────────────────────────────────────

async def is_admin_authenticated(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT authenticated FROM admins WHERE user_id=?", (user_id,)
        )
        row = await cursor.fetchone()
        return row and row[0] == 1


async def set_admin_authenticated(user_id, value: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO admins (user_id, authenticated) VALUES (?, ?)",
            (user_id, 1 if value else 0)
        )
        await db.commit()


async def get_admin_password() -> str:
    """Получить текущий пароль из БД или вернуть дефолтный из config."""
    import config
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key='admin_password'"
        )
        row = await cursor.fetchone()
        if row:
            return row[0]
        return config.ADMIN_PASSWORD


async def set_admin_password(new_password: str):
    """Обновить пароль в БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ('admin_password', new_password)
        )
        await db.commit()