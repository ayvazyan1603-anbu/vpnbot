from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ℹ️ Инфо о VPN", callback_data="info")],
        [InlineKeyboardButton(text="💰 Цены", callback_data="prices")],
        [InlineKeyboardButton(text="🛒 Купить", callback_data="buy")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
    ])

def buy_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"1 месяц — {config.PRICE_1_MONTH}₽",
            callback_data="plan_1_month"
        )],
        [InlineKeyboardButton(
            text=f"3 месяца — {config.PRICE_3_MONTHS}₽",
            callback_data="plan_3_months"
        )],
        [InlineKeyboardButton(
            text=f"6 месяцев — {config.PRICE_6_MONTHS}₽",
            callback_data="plan_6_months"
        )],
        [InlineKeyboardButton(
            text=f"1 год — {config.PRICE_12_MONTHS}₽",
            callback_data="plan_12_months"
        )],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ])

def back_to_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")]
    ])

def admin_order_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}"),
        ]
    ])

PLAN_NAMES = {
    "1_month": "1 месяц",
    "3_months": "3 месяца",
    "6_months": "6 месяцев",
    "12_months": "1 год",
}

PLAN_PRICES = {
    "1_month": lambda: config.PRICE_1_MONTH,
    "3_months": lambda: config.PRICE_3_MONTHS,
    "6_months": lambda: config.PRICE_6_MONTHS,
    "12_months": lambda: config.PRICE_12_MONTHS,
}
