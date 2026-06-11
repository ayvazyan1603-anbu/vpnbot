from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import database as db
from keyboards import main_menu, buy_menu, back_to_main, admin_order_keyboard, PLAN_NAMES, PLAN_PRICES

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
        "ℹ️ *О нашем VPN*\n\n"
        "Здесь вы можете написать любой текст о вашем VPN-сервисе.\n\n"
        "Например:\n"
        "• Протокол: VLESS\n"
        "• Сервер: Европа / США\n"
        "• Скорость: до 1 Гбит/с\n"
        "• Без логов\n"
        "• Работает в России ✅\n\n"
        "_Замените этот текст на свой в файле `handlers_user.py`_"
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=back_to_main())


# ── Цены ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "prices")
async def show_prices(call: CallbackQuery):
    text = (
        "💰 *Тарифы*\n\n"
        f"🗓 1 месяц — *{config.PRICE_1_MONTH}₽*\n"
        f"🗓 3 месяца — *{config.PRICE_3_MONTHS}₽*\n"
        f"🗓 6 месяцев — *{config.PRICE_6_MONTHS}₽*\n"
        f"🗓 1 год — *{config.PRICE_12_MONTHS}₽*\n\n"
        "Нажмите *Купить* в главном меню, чтобы оформить заказ."
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=back_to_main())


# ── Поддержка ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "support")
async def show_support(call: CallbackQuery):
    text = (
        f"🆘 *Поддержка*\n\n"
        f"По всем вопросам пишите: @{config.SUPPORT_USERNAME}\n\n"
        "Время ответа: обычно до 1 часа."
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=back_to_main())


# ── Купить ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "buy")
async def show_buy(call: CallbackQuery):
    await call.message.edit_text(
        "🛒 *Выберите тариф:*",
        parse_mode="Markdown",
        reply_markup=buy_menu()
    )


@router.callback_query(F.data.startswith("plan_"))
async def select_plan(call: CallbackQuery, state: FSMContext):
    plan = call.data.replace("plan_", "")
    plan_name = PLAN_NAMES.get(plan, plan)
    price = PLAN_PRICES[plan]()

    await state.update_data(plan=plan, price=price, plan_name=plan_name)
    await state.set_state(OrderStates.waiting_screenshot)

    text = (
        f"✅ Вы выбрали: *{plan_name}* — *{price}₽*\n\n"
        f"💳 Оплатите на реквизиты:\n`{config.PAYMENT_DETAILS}`\n\n"
        "📸 После оплаты отправьте *скриншот чека* в этот чат.\n\n"
        "⚠️ Заказ активируется после проверки оплаты администратором."
    )
    await call.message.edit_text(text, parse_mode="Markdown")


# ── Приём скриншота ───────────────────────────────────────────────────────────

@router.message(OrderStates.waiting_screenshot, F.photo)
async def receive_screenshot(message: Message, state: FSMContext, bot=None):
    data = await state.get_data()
    plan = data["plan"]
    price = data["price"]
    plan_name = data["plan_name"]

    user = message.from_user
    file_id = message.photo[-1].file_id

    # Сохраняем заказ
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

    # Уведомляем администратора
    if bot:
        username_str = f"@{user.username}" if user.username else "без username"
        admin_text = (
            f"🔔 *Новый заказ #{order_id}*\n\n"
            f"👤 Пользователь: {user.full_name} ({username_str})\n"
            f"🆔 ID: `{user.id}`\n"
            f"📦 Тариф: {plan_name}\n"
            f"💰 Сумма: {price}₽\n\n"
            "📸 Скриншот чека прикреплён ниже."
        )
        await bot.send_photo(
            chat_id=config.ADMIN_ID,
            photo=file_id,
            caption=admin_text,
            parse_mode="Markdown",
            reply_markup=admin_order_keyboard(order_id)
        )


@router.message(OrderStates.waiting_screenshot)
async def wrong_screenshot(message: Message):
    await message.answer("📸 Пожалуйста, отправьте именно *фото* (скриншот чека).", parse_mode="Markdown")
