from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import database as db
import xui_client
from keyboards import PLAN_NAMES

router = Router()


class AdminStates(StatesGroup):
    waiting_password = State()
    waiting_reject_reason = State()


# ── /admin ────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if await db.is_admin_authenticated(message.from_user.id):
        await message.answer("✅ Вы уже в админ-панели.\n\nКоманды:\n/orders — список заявок\n/logout — выйти")
        return
    await state.set_state(AdminStates.waiting_password)
    await message.answer("🔐 Введите пароль администратора:")


@router.message(AdminStates.waiting_password)
async def check_password(message: Message, state: FSMContext):
    await message.delete()  # удаляем сообщение с паролем из чата
    if message.text == config.ADMIN_PASSWORD:
        await db.set_admin_authenticated(message.from_user.id, True)
        await state.clear()
        await message.answer(
            "✅ Авторизация успешна!\n\n"
            "Команды:\n"
            "/orders — список заявок\n"
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
        username_str = f"@{order['username']}" if order['username'] else "без username"
        text = (
            f"📦 *Заказ #{order['id']}*\n"
            f"👤 {order['full_name']} ({username_str})\n"
            f"🆔 ID: `{order['user_id']}`\n"
            f"📅 Тариф: {plan_name}\n"
            f"💰 Сумма: {order['price']}₽\n"
            f"🕐 Создан: {order['created_at']}"
        )
        from keyboards import admin_order_keyboard
        if order["screenshot_file_id"]:
            await message.answer_photo(
                photo=order["screenshot_file_id"],
                caption=text,
                parse_mode="Markdown",
                reply_markup=admin_order_keyboard(order["id"])
            )
        else:
            await message.answer(text, parse_mode="Markdown", reply_markup=admin_order_keyboard(order["id"]))


# ── Одобрить заказ ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("approve_"))
async def approve_order(call: CallbackQuery):
    if not await db.is_admin_authenticated(call.from_user.id):
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
    await call.message.edit_caption(
        caption=call.message.caption + "\n\n⏳ *Обрабатывается...*",
        parse_mode="Markdown"
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

        # Сообщение пользователю
        user_text = (
            f"🎉 *Ваш заказ #{order_id} одобрен!*\n\n"
            f"📦 Тариф: {plan_name}\n"
            f"⏳ Срок: {result['expire_days']} дней\n\n"
            f"🔗 *Ваша ссылка подключения:*\n"
            f"`{result['link']}`\n\n"
            "📲 Скопируйте ссылку и вставьте в приложение (v2rayNG, Hiddify, Streisand и др.)\n\n"
            f"По вопросам: @{config.SUPPORT_USERNAME}"
        )

        await call.bot.send_message(
            chat_id=order["user_id"],
            text=user_text,
            parse_mode="Markdown"
        )

        # Обновляем сообщение в чате админа
        await call.message.edit_caption(
            caption=call.message.caption + f"\n\n✅ *Одобрено. VPN выдан.*\nEmail: `{result['email']}`",
            parse_mode="Markdown"
        )

    except Exception as e:
        await call.message.edit_caption(
            caption=call.message.caption + f"\n\n❌ *Ошибка создания VPN:* `{str(e)}`",
            parse_mode="Markdown"
        )
        await call.answer(f"Ошибка: {e}", show_alert=True)


# ── Отклонить заказ ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reject_"))
async def reject_order(call: CallbackQuery, state: FSMContext):
    if not await db.is_admin_authenticated(call.from_user.id):
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
    if not await db.is_admin_authenticated(message.from_user.id):
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

    # Сообщение пользователю
    user_text = (
        f"❌ *Ваш заказ #{order_id} отклонён.*\n\n"
        f"📝 Причина: {reason}\n\n"
        f"Если у вас есть вопросы — пишите @{config.SUPPORT_USERNAME}"
    )
    await message.bot.send_message(
        chat_id=order["user_id"],
        text=user_text,
        parse_mode="Markdown"
    )

    await message.answer(f"✅ Заказ #{order_id} отклонён. Пользователь уведомлён.")
