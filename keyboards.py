from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config

# ── Кастомные emoji ID ────────────────────────────────────────────────────────
EMOJI_IDS = {
    "gear":      "5202011466328223499",  # ⚙️
    "info":      "5201852062911998991",  # ℹ️
    "bot":       "5202132137729371109",  # 🤖
    "phone":     "5202100926202033066",  # 📞
    "user":      "5202196991735538597",  # 👤
    "block":     "5201832795688710838",  # 🚫
    "home":      "5201946358918981962",  # 🏡
    "flash":     "5201846625483402589",  # ⚡️
    "coin":      "5202218329133070219",  # 🪙
    "shop":      "5201844628323607621",  # 🏪
    "chat":      "5201740445301908802",  # 💬
    "link":      "5201965647617107445",  # 🔗
    "down":      "5201889991768194046",  # ⬇️
    "mega":      "5201873271460507860",  # 📣
    "folder":    "5202139310324756410",  # 🗂
    "tag":       "5201790069354045799",  # 🏷
    "check":     "5202120777540873332",  # ✅
    "friends":   "5201769659669459193",  # 👥
    "briefcase": "5202064758282433388",  # 💼
    "cross":     "5774077015388852135",  # ❌
}


def _btn(emoji_key: str, label: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    """Создаёт inline-кнопку с кастомным эмодзи-иконкой."""
    kwargs = {
        "text": label,
        "icon_custom_emoji_id": EMOJI_IDS[emoji_key],
    }
    if url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = callback_data
    return InlineKeyboardButton(**kwargs)


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("info",  "О сервисе",  "info")],
        [_btn("tag",   "Тарифы",     "prices")],
        [_btn("shop",  "Купить VPN", "buy")],
        [_btn("user",  "Профиль",    "profile")],
        [_btn("phone", "Поддержка",  "support")],
    ])


def buy_menu(prices: dict = None):
    if prices is None:
        prices = {
            "price_1_month": config.PRICE_1_MONTH,
            "price_3_months": config.PRICE_3_MONTHS,
            "price_6_months": config.PRICE_6_MONTHS,
            "price_12_months": config.PRICE_12_MONTHS,
        }
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("flash", f"1 месяц — {prices['price_1_month']}₽",    "plan_1_month")],
        [_btn("coin",  f"3 месяца — {prices['price_3_months']}₽",  "plan_3_months")],
        [_btn("shop",  f"6 месяцев — {prices['price_6_months']}₽", "plan_6_months")],
        [_btn("gear",  f"1 год — {prices['price_12_months']}₽",    "plan_12_months")],
        [_btn("home",  "Главное меню", "back_main")],
    ])


def back_to_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("home", "Главное меню", "back_main")]
    ])


def back_to_profile():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("user", "Мой профиль", "profile")],
        [_btn("home", "Главное меню", "back_main")]
    ])


def profile_menu(bonus_days: int = 0):
    """Меню профиля пользователя."""
    buttons = [
        [_btn("friends",   "5 дней за друга",          "referral")],
        [_btn("shop",      "Подарить подписку",        "gift")],
        [_btn("phone",     "Помощь",                   "help_menu")],
        [_btn("flash",     "Получить пробные 1 день",  "trial")],
    ]
    if bonus_days > 0:
        buttons.insert(0, [_btn("coin", f"Активировать {bonus_days} бонусных дн.", "activate_bonus")])
    buttons.append([_btn("home", "Главное меню", "back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def referral_menu(ref_link: str):
    """Меню реферальной программы."""
    share_url = f"https://t.me/share/url?url={ref_link}&text=Присоединяйся к GHOST VPN! Получи 5 дней бесплатно!"
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("down",      "Поделиться", url=share_url)],
        [_btn("briefcase", "Заработать с нами", "partner")],
        [_btn("home",      "Главное меню",      "back_main")],
    ])


def partner_menu(has_link: bool = False):
    """Меню партнёрской программы."""
    buttons = []
    if not has_link:
        buttons.append([_btn("link", "Создать партнерскую ссылку", "create_partner_link")])
    buttons.append([_btn("phone", "Вывод средств (Поддержка)", "support")])
    buttons.append([_btn("home", "Главное меню", "back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def gift_tariffs_menu(prices: dict = None):
    """Выбор тарифа для подарка."""
    if prices is None:
        prices = {
            "price_1_month": config.PRICE_1_MONTH,
            "price_3_months": config.PRICE_3_MONTHS,
            "price_6_months": config.PRICE_6_MONTHS,
            "price_12_months": config.PRICE_12_MONTHS,
        }
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("flash", f"1 месяц — {prices['price_1_month']}₽",    "giftplan_1_month")],
        [_btn("coin",  f"3 месяца — {prices['price_3_months']}₽",  "giftplan_3_months")],
        [_btn("shop",  f"6 месяцев — {prices['price_6_months']}₽", "giftplan_6_months")],
        [_btn("gear",  f"1 год — {prices['price_12_months']}₽",    "giftplan_12_months")],
        [_btn("cross", "Отмена", "profile")],
    ])


def admin_order_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            _btn("check", "Одобрить",  f"approve_{order_id}"),
            _btn("cross", "Отклонить", f"reject_{order_id}"),
        ]
    ])


def admin_prices_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("flash", "1 месяц",   "setprice_1_month")],
        [_btn("coin",  "3 месяца",  "setprice_3_months")],
        [_btn("shop",  "6 месяцев", "setprice_6_months")],
        [_btn("gear",  "1 год",     "setprice_12_months")],
        [_btn("cross", "Отмена",    "setprice_cancel")],
    ])


PLAN_NAMES = {
    "1_month": "1 месяц",
    "3_months": "3 месяца",
    "6_months": "6 месяцев",
    "12_months": "1 год",
    "trial": "1 день (Пробный)",
    "bonus": "Бонусный период",
}

PLAN_PRICE_KEYS = {
    "1_month": "price_1_month",
    "3_months": "price_3_months",
    "6_months": "price_6_months",
    "12_months": "price_12_months",
}

PLAN_PRICES = {
    "1_month": lambda: config.PRICE_1_MONTH,
    "3_months": lambda: config.PRICE_3_MONTHS,
    "6_months": lambda: config.PRICE_6_MONTHS,
    "12_months": lambda: config.PRICE_12_MONTHS,
}
