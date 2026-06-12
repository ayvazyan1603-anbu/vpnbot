from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import html
import logging
import config
import database as db
from keyboards import main_menu, buy_menu, back_to_main, admin_order_keyboard, PLAN_NAMES, PLAN_PRICE_KEYS

router = Router()

class OrderStates(StatesGroup):
    waiting_screenshot = State()

# ── /start ────────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать в VPN-магазин!\n\nВыберите нужный раздел:",
        reply_markup=main_menu()
    )

# ── Главное меню ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "👋 Главное меню. Выберите нужный раздел:",
        reply_markup=main_menu()
    )

# ── Инфо о VPN ───────────────────────────────────────────────────────────────
@router.callback_query(F.data == "info")
async def show_info(call: CallbackQuery):
    text = (
        "ℹ️ <b>О нашем VPN</b>\n\n"
        "Здесь вы можете написать любой текст о вашем VPN-сервисе.\n\n"
        "Например:\n"
        "• Протокол: VLESS\n"
        "• Сервер: Европа / США\n"
        "• Скорость: до 1 Гбит/с\n"
        "• Без логов\n"
        "• Работает в России ✅"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_main())

# ── Цены ──────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "prices")
async def show_prices(call: CallbackQuery):
    prices = await db.get_prices()
    text = (
        "💰 <b>Тарифы</b>\n\n"
        f"🗓 1 месяц — <b>{prices.get('price_1_month', '?')}₽</b>\n"
        f"🗓 3 месяца — <b>{prices.get('price_3_months', '?')}₽</b>\n"
        f"🗓 6 месяцев — <b>{prices.get('price_6_months', '?')}₽</b>\n"
        f"🗓 1 год — <b>{prices.get('price_12_months', '?')}₽</b>\n\n"
        "Нажмите <b>Купить</b> в главном меню, чтобы оформить заказ."
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_main())

# ── Поддержка ─────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "support")
async def show_support(call: CallbackQuery):
    text = (
        f"🆘 <b>Поддержка</b>\n\n"
        f"По всем вопросам пишите: @{config.SUPPORT_USERNAME}\n\n"
        "Время ответа: обычно до 1 часа."
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_main())

# ── Купить ────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "buy")
async def show_buy(call: CallbackQuery):
    prices = await db.get_prices()
    await call.message.edit_text(
        "🛒 <b>Выберите тариф:</b>",
        parse_mode="HTML",
        reply_markup=buy_menu(prices)
    )

@router.callback_query(F.data.startswith("plan_"))
async def select_plan(call: CallbackQuery, state: FSMContext):
    plan = call.data.replace("plan_", "")
    plan_name = PLAN_NAMES.get(plan, plan)

    prices = await db.get_prices()
    price_key = PLAN_PRICE_KEYS.get(plan)
    price = prices.get(price_key, 0)

    await state.update_data(plan=plan, price=price, plan_name=plan_name)
    await state.set_state(OrderStates.waiting_screenshot)

    text = (
        f"✅ Вы выбрали: <b>{html.escape(plan_name)}</b> — <b>{price}₽</b>\n\n"
        f"💳 Оплатите на реквизиты:\n<code>{html.escape(config.PAYMENT_DETAILS)}</code>\n\n"
        "📸 После оплаты отправьте <b>скриншот чека</b> в этот чат.\n\n"
        "⚠️ Заказ активируется после проверки оплаты администратором."
    )
    await call.message.edit_text(text, parse_mode="HTML")

# ── Приём скриншота ───────────────────────────────────────────────────────────
@router.message(OrderStates.waiting_screenshot, F.photo)
async def receive_screenshot(message: Message, state: FSMContext, bot=None):
    data = await state.get_data()
    plan = data["plan"]
    price = data["price"]
    plan_name = data["plan_name"]

    user = message.from_user
    file_id = message.photo[-1].file_id

    order_id = await db.create_order(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name,
        plan=plan,
        price=price,
    )
    await db.update_order_screenshot(order_id, file_id)
    await state.clear()

    await message.answer(
        f"✅ Ваш заказ #{order_id} получен!\n"
        "Ожидайте подтверждения от администратора. Обычно это занимает до 30 минут."
    )

    if bot:
        username_str = f"@{html.escape(user.username)}" if user.username else "без username"
        full_name_str = html.escape(user.full_name) if user.full_name else "Без имени"
        
        # Перевели шаблон уведомления на HTML, чтобы он полностью совпадал с выводом /orders
        admin_text = (
            f"📦 <b>Заказ #{order_id}</b>\n"
            f"👤 {full_name_str} ({username_str})\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📅 Тариф: {html.escape(plan_name)}\n"
            f"💰 Сумма: {price}₽\n\n"
            "📸 Скриншот чека прикреплён ниже."
        )
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=admin_text,
                    parse_mode="HTML",
                    reply_markup=admin_order_keyboard(order_id)
                )
            except Exception as e:
                logging.getLogger(__name__).warning(
                    f"Не удалось отправить уведомление админу {admin_id}: {e}"
                )

@router.message(OrderStates.waiting_screenshot)
async def wrong_screenshot(message: Message):
    await message.answer("📸 Пожалуйста, отправьте именно <b>фото</b> (скриншот чека).", parse_mode="HTML")