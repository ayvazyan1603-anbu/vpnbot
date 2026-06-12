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
        await db.commit()
    # Seed prices from config if not yet in DB
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

async def create_order(user_id, username, full_name, plan, price):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO orders (user_id, username, full_name, plan, price) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, full_name, plan, price)
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