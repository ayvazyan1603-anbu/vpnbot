import html
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import database as db
import xui_client
from keyboards import PLAN_NAMES, PLAN_PRICE_KEYS, admin_prices_keyboard

router = Router()

class AdminStates(StatesGroup):
    waiting_password = State()
    waiting_reject_reason = State()
    waiting_new_price = State()

# ── /admin ────────────────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS:
        return
        
    if await db.is_admin_authenticated(message.from_user.id):
        await message.answer(
            "✅ Вы уже в админ-панели.\n\n"
            "Команды:\n"
            "/orders — список заявок\n"
            "/prices — управление ценами\n"
            "/logout — выйти"
        )
        return
    await state.set_state(AdminStates.waiting_password)
    await message.answer("🔐 Введите пароль администратора:")

@router.message(AdminStates.waiting_password)
async def check_password(message: Message, state: FSMContext):
    await message.delete()
    if message.from_user.id not in config.ADMIN_IDS:
        await state.clear()
        return

    if message.text == config.ADMIN_PASSWORD:
        await db.set_admin_authenticated(message.from_user.id, True)
        await state.clear()
        await message.answer(
            "✅ Авторизация успешна!\n\n"
            "Команды:\n"
            "/orders — список заявок\n"
            "/prices — управление ценами\n"
            "/logout — выйти из админки"
        )
    else:
        await state.clear()
        await message.answer("❌ Неверный пароль.")

@router.message(Command("logout"))
async def cmd_logout(message: Message):
    await db.set_admin_authenticated(message.from_user.id, False)
    await message.answer("👋 Вы вышли из админ-панели.")

# ── /orders ───────────────────────────────────────────────────────────────────
@router.message(Command("orders"))
async def cmd_orders(message: Message):
    if not await db.is_admin_authenticated(message.from_user.id):
        await message.answer("⛔ Нет доступа. Используйте /admin")
        return

    orders = await db.get_pending_orders()
    if not orders:
        await message.answer("📭 Нет ожидающих заявок.")
        return

    await message.answer(f"📋 Ожидающих заявок: {len(orders)}\n\nВыведу каждую отдельно...")

    for order in orders:
        plan_name = PLAN_NAMES.get(order["plan"], order["plan"])
        username_str = f"@{html.escape(order['username'])}" if order['username'] else "без username"
        full_name_str = html.escape(order['full_name']) if order['full_name'] else "Без имени"
        
        text = (
            f"📦 <b>Заказ #{order['id']}</b>\n"
            f"👤 {full_name_str} ({username_str})\n"
            f"🆔 ID: <code>{order['user_id']}</code>\n"
            f"📅 Тариф: {html.escape(plan_name)}\n"
            f"💰 Сумма: {order['price']}₽\n"
            f"🕐 Создан: {order['created_at']}"
        )
        from keyboards import admin_order_keyboard
        if order["screenshot_file_id"]:
            await message.answer_photo(
                photo=order["screenshot_file_id"],
                caption=text,
                parse_mode="HTML",
                reply_markup=admin_order_keyboard(order["id"])
            )
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=admin_order_keyboard(order["id"]))

# ── /prices ───────────────────────────────────────────────────────────────────
@router.message(Command("prices"))
async def cmd_prices(message: Message):
    if not await db.is_admin_authenticated(message.from_user.id):
        await message.answer("⛔ Нет доступа. Используйте /admin")
        return

    prices = await db.get_prices()
    text = (
        "💰 <b>Текущие цены:</b>\n\n"
        f"• 1 месяц — {prices.get('price_1_month', '?')}₽\n"
        f"• 3 месяца — {prices.get('price_3_months', '?')}₽\n"
        f"• 6 месяцев — {prices.get('price_6_months', '?')}₽\n"
        f"• 1 год — {prices.get('price_12_months', '?')}₽\n\n"
        "Выберите тариф для изменения цены:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=admin_prices_keyboard())

# ── Изменение цены ────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("setprice_"))
async def cb_setprice(call: CallbackQuery, state: FSMContext):
    if not await db.is_admin_authenticated(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    plan = call.data[len("setprice_"):]
    if plan == "cancel":
        await call.message.edit_text("❌ Изменение цен отменено.")
        return

    plan_label = {
        "1_month": "1 месяц",
        "3_months": "3 месяца",
        "6_months": "6 месяцев",
        "12_months": "1 год",
    }.get(plan, plan)

    prices = await db.get_prices()
    price_key = PLAN_PRICE_KEYS.get(plan)
    current = prices.get(price_key, "?")

    await state.set_state(AdminStates.waiting_new_price)
    await state.update_data(price_plan=plan, price_key=price_key)
    await call.answer()
    await call.message.edit_text(
        f"✏️ <b>Изменение цены: {html.escape(plan_label)}</b>\n\n"
        f"Текущая цена: <b>{current}₽</b>\n\n"
        "Введите новую цену (только число, в рублях):",
        parse_mode="HTML"
    )

@router.message(AdminStates.waiting_new_price)
async def process_new_price(message: Message, state: FSMContext):
    if not await db.is_admin_authenticated(message.from_user.id):
        await state.clear()
        return

    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Некорректная цена. Введите положительное целое число:")
        return

    new_price = int(text)
    data = await state.get_data()
    price_key = data["price_plan"]
    db_key = data["price_key"]

    plan_label = {
        "1_month": "1 месяц",
        "3_months": "3 месяца",
        "6_months": "6 месяцев",
        "12_months": "1 год",
    }.get(price_key, price_key)

    await db.set_price(db_key, new_price)
    await state.clear()

    prices = await db.get_prices()
    updated_text = (
        f"✅ <b>Цена обновлена!</b>\n\n"
        f"Тариф «{html.escape(plan_label)}» → <b>{new_price}₽</b>\n\n"
        "💰 <b>Все текущие цены:</b>\n"
        f"• 1 месяц — {prices.get('price_1_month', '?')}₽\n"
        f"• 3 месяца — {prices.get('price_3_months', '?')}₽\n"
        f"• 6 месяцев — {prices.get('price_6_months', '?')}₽\n"
        f"• 1 год — {prices.get('price_12_months', '?')}₽"
    )
    await message.answer(updated_text, parse_mode="HTML", reply_markup=admin_prices_keyboard())

# ── Одобрить заказ ────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("approve_"))
async def approve_order(call: CallbackQuery):
    if call.from_user.id not in config.ADMIN_IDS and not await db.is_admin_authenticated(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split("_")[1])
    order = await db.get_order(order_id)

    if not order:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return

    if order["status"] != "pending":
        await call.answer("⚠️ Заказ уже обработан", show_alert=True)
        return

    await call.answer("⏳ Создаю VPN-аккаунт...")
    
    # ИСПРАВЛЕНИЕ: Берем текст БЕЗ повторного html.escape, так как он уже чистый
    base_caption = html.escape(call.message.caption) if call.message.caption else ""
    await call.message.edit_caption(
        caption=base_caption + "\n\n⏳ <b>Обрабатывается...</b>",
        parse_mode="HTML"
    )

    try:
        result = await xui_client.add_client(
            user_id=order["user_id"],
            plan=order["plan"]
        )

        await db.update_order_status(
            order_id,
            status="approved",
            xui_client_id=result["client_id"],
            xui_email=result["email"]
        )

        plan_name = PLAN_NAMES.get(order["plan"], order["plan"])

        user_text = (
            f"🎉 <b>Ваш заказ #{order_id} одобрен!</b>\n\n"
            f"📦 Тариф: {html.escape(plan_name)}\n"
            f"⏳ Срок: {result['expire_days']} дней\n\n"
            f"🔗 <b>Ваша ссылка подключения:</b>\n"
            f"<code>{result['link']}</code>\n\n"
            "📲 Скопируйте ссылку и вставьте в приложение (v2rayNG, Hiddify, Streisand и др.)\n\n"
            f"По вопросам: @{config.SUPPORT_USERNAME}"
        )

        await call.bot.send_message(
            chat_id=order["user_id"],
            text=user_text,
            parse_mode="HTML"
        )

        # ИСПРАВЛЕНИЕ: Формируем финальную подпись с нуля, чтобы разметка гарантированно не поплыла
        await call.message.edit_caption(
            caption=base_caption + f"\n\n✅ <b>Одобрено. VPN выдан.</b>\nEmail: <code>{html.escape(result['email'])}</code>",
            parse_mode="HTML"
        )

    except Exception as e:
        await call.message.edit_caption(
            caption=base_caption + f"\n\n❌ <b>Ошибка создания VPN:</b> <code>{html.escape(str(e))}</code>",
            parse_mode="HTML"
        )
        await call.answer(f"Ошибка: {e}", show_alert=True)

# ── Отклонить заказ ───────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("reject_"))
async def reject_order(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in config.ADMIN_IDS and not await db.is_admin_authenticated(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split("_")[1])
    order = await db.get_order(order_id)

    if not order or order["status"] != "pending":
        await call.answer("⚠️ Заказ уже обработан или не найден", show_alert=True)
        return

    await state.update_data(reject_order_id=order_id, reject_msg_id=call.message.message_id)
    await state.set_state(AdminStates.waiting_reject_reason)
    await call.answer()
    await call.message.answer("✏️ Напишите причину отказа (она будет отправлена пользователю):")

@router.message(AdminStates.waiting_reject_reason)
async def process_reject_reason(message: Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS and not await db.is_admin_authenticated(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    order_id = data["reject_order_id"]
    reason = message.text
    await state.clear()

    order = await db.get_order(order_id)
    if not order:
        await message.answer("❌ Заказ не найден.")
        return

    await db.update_order_status(order_id, status="rejected")

    user_text = (
        f"❌ <b>Ваш заказ #{order_id} отклонён.</b>\n\n"
        f"📝 Причина: {html.escape(reason)}\n\n"
        f"Если у вас есть вопросы — пишите @{config.SUPPORT_USERNAME}"
    )
    await message.bot.send_message(
        chat_id=order["user_id"],
        text=user_text,
        parse_mode="HTML"
    )

    await message.answer(f"✅ Заказ #{order_id} отклонён. Пользователь уведомлён.")