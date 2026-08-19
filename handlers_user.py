from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, FSInputFile
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from pathlib import Path

import html
import logging
import config
import database as db
import xui_client
from keyboards import (
    main_menu, buy_menu, back_to_main, back_to_profile, profile_menu,
    referral_menu, partner_menu, gift_tariffs_menu, admin_order_keyboard,
    PLAN_NAMES, PLAN_PRICE_KEYS
)
from emojis import (
    EMOJI_GEAR, EMOJI_INFO, EMOJI_BOT, EMOJI_PHONE,
    EMOJI_USER, EMOJI_BLOCK, EMOJI_HOME, EMOJI_FLASH,
    EMOJI_COIN, EMOJI_SHOP, EMOJI_CHAT, EMOJI_LINK,
    EMOJI_DOWN, EMOJI_MEGA, EMOJI_FOLDER, EMOJI_TAG,
    EMOJI_CHECK, EMOJI_FRIENDS, EMOJI_BRIEFCASE, EMOJI_CROSS
)

router = Router()

IMAGES_DIR = Path(__file__).parent / "images"

def get_image(filename: str) -> FSInputFile | None:
    path = IMAGES_DIR / filename
    if path.exists():
        return FSInputFile(path)
    return None

async def send_or_edit_banner(
    event: Message | CallbackQuery,
    image_name: str,
    caption: str,
    reply_markup=None,
    parse_mode: str = "HTML"
):
    """Универсальная отправка или плавное обновление баннера и кнопок."""
    image = get_image(image_name)

    if isinstance(event, CallbackQuery):
        try:
            if image and event.message.photo:
                await event.message.edit_media(
                    media=InputMediaPhoto(media=image, caption=caption, parse_mode=parse_mode),
                    reply_markup=reply_markup
                )
                return
            elif image:
                await event.message.delete()
                await event.message.answer_photo(
                    photo=image,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                return
            else:
                await event.message.edit_text(caption, parse_mode=parse_mode, reply_markup=reply_markup)
                return
        except Exception:
            try:
                if image:
                    await event.message.answer_photo(
                        photo=image,
                        caption=caption,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup
                    )
                else:
                    await event.message.answer(caption, parse_mode=parse_mode, reply_markup=reply_markup)
            except Exception as e:
                logging.getLogger(__name__).error(f"Ошибка при отправке баннера: {e}")
    else:
        if image:
            await event.answer_photo(
                photo=image,
                caption=caption,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        else:
            await event.answer(caption, parse_mode=parse_mode, reply_markup=reply_markup)


class OrderStates(StatesGroup):
    waiting_screenshot = State()
    waiting_gift_recipient = State()
    waiting_gift_screenshot = State()

# ── /start ────────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject = None, bot=None):
    await state.clear()
    user = message.from_user
    await db.get_or_create_user(user.id, user.username or "", user.full_name or "")

    args = command.args if command else None
    if args:
        if args.startswith("ref"):
            try:
                referrer_id = int(args.replace("ref", ""))
                if referrer_id != user.id:
                    is_new_ref = await db.set_referrer(user.id, referrer_id, is_partner=False)
                    if is_new_ref:
                        await db.add_referral_bonus(referrer_id, user.id, config.REFERRAL_BONUS_DAYS)
                        if bot:
                            try:
                                await bot.send_message(
                                    chat_id=referrer_id,
                                    text=(
                                        f"🎉 {EMOJI_BOT} <b>Новый друг присоединился по вашей ссылке!</b>\n\n"
                                        f"Пользователь {html.escape(user.full_name)} зарегистрировался.\n"
                                        f"🎁 Вам начислено <b>+{config.REFERRAL_BONUS_DAYS} бонусных дней</b>!"
                                    ),
                                    parse_mode="HTML"
                                )
                            except Exception:
                                pass
            except Exception as e:
                logging.getLogger(__name__).warning(f"Ошибка парсинга реф-кода: {e}")
        elif args.startswith("partner"):
            try:
                partner_id = int(args.replace("partner", ""))
                if partner_id != user.id:
                    await db.set_referrer(user.id, partner_id, is_partner=True)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Ошибка парсинга партнёр-кода: {e}")

    caption = f"👋 {EMOJI_BOT} <b>Добро пожаловать в GHOST VPN!</b>\n\nВыберите нужный раздел:"
    await send_or_edit_banner(message, "main_menu.jpg", caption, reply_markup=main_menu())

# ── Главное меню ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    caption = f"{EMOJI_HOME} <b>Главное меню.</b> Выберите нужный раздел:"
    await send_or_edit_banner(call, "main_menu.jpg", caption, reply_markup=main_menu())

# ── Инфо о VPN ───────────────────────────────────────────────────────────────
@router.callback_query(F.data == "info")
async def show_info(call: CallbackQuery):
    text = (
        f"<b>{EMOJI_INFO} Почему выбирают GHOST VPN?</b>\n\n"
        "Надоело, что не грузит Telegram и сервисы?\n"
        "Мы точно знаем, как вам помочь!\n\n"
        f"{EMOJI_FLASH} <b>Скорость до 1 Гбит/с</b> — YouTube в 4K без задержек\n"
        f"{EMOJI_BLOCK} <b>Обход DPI</b> — стабильная работа в РФ без блокировок\n"
        f"{EMOJI_GEAR} <b>No-Logs & Безопасность</b> — полная анонимность\n"
    )
    await send_or_edit_banner(call, "info.jpg", text, reply_markup=back_to_main())

# ── Цены ──────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "prices")
async def show_prices(call: CallbackQuery):
    prices = await db.get_prices()
    text = (
        f"{EMOJI_TAG} <b>Тарифы GHOST VPN</b>\n\n"
        f"{EMOJI_FLASH} 1 месяц — <b>{prices.get('price_1_month', '?')}₽</b>\n"
        f"{EMOJI_COIN} 3 месяца — <b>{prices.get('price_3_months', '?')}₽</b>\n"
        f"{EMOJI_SHOP} 6 месяцев — <b>{prices.get('price_6_months', '?')}₽</b>\n"
        f"{EMOJI_GEAR} 1 год — <b>{prices.get('price_12_months', '?')}₽</b>\n\n"
        "Нажмите <b>Купить VPN</b> в меню ниже, чтобы оформить заказ."
    )
    await send_or_edit_banner(call, "buy_tariffs.jpg", text, reply_markup=back_to_main())

# ── Поддержка ─────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "support")
async def show_support(call: CallbackQuery):
    text = (
        f"{EMOJI_PHONE} <b>Служба поддержки GHOST VPN</b>\n\n"
        f"{EMOJI_CHAT} По всем вопросам пишите:\n👉 @{config.SUPPORT_USERNAME}\n\n"
        "⏱ Время ответа: обычно до 1 часа."
    )
    await send_or_edit_banner(call, "main_menu.jpg", text, reply_markup=back_to_main())

# ── Купить ────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "buy")
async def show_buy(call: CallbackQuery):
    prices = await db.get_prices()
    text = f"{EMOJI_SHOP} <b>Выберите подходящий тариф:</b>"
    await send_or_edit_banner(call, "buy_tariffs.jpg", text, reply_markup=buy_menu(prices))

@router.callback_query(F.data.startswith("plan_"))
async def select_plan(call: CallbackQuery, state: FSMContext):
    plan = call.data.replace("plan_", "")
    plan_name = PLAN_NAMES.get(plan, plan)

    prices = await db.get_prices()
    price_key = PLAN_PRICE_KEYS.get(plan)
    price = prices.get(price_key, 0)

    await state.update_data(plan=plan, price=price, plan_name=plan_name, is_gift=False)
    await state.set_state(OrderStates.waiting_screenshot)

    text = (
        f"{EMOJI_CHECK} Вы выбрали: <b>{html.escape(plan_name)}</b> — <b>{price}₽</b>\n\n"
        f"{EMOJI_GEAR} <b>Реквизиты для оплаты:</b>\n"
        f"<code>{html.escape(config.PAYMENT_DETAILS)}</code> (Обязательно OZON Банк / СБП)\n\n"
        f"{EMOJI_CHAT} <b>После оплаты отправьте скриншот чека в этот чат.</b>\n\n"
        "⚠️ Заказ активируется после проверки оплаты администратором."
    )
    await send_or_edit_banner(call, "payment_instruction.jpg", text, reply_markup=back_to_main())

# ── Профиль пользователя ──────────────────────────────────────────────────────
@router.callback_query(F.data == "profile")
async def show_profile(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = call.from_user
    profile = await db.get_or_create_user(user.id, user.username or "", user.full_name or "")
    active_vpn = await db.get_active_vpn(user.id)

    bonus_days = profile["bonus_days"] if profile else 0
    referral_count = profile["referral_count"] if profile else 0
    partner_earnings = profile["partner_earnings"] if profile else 0

    if active_vpn and active_vpn["xui_client_id"]:
        plan_label = PLAN_NAMES.get(active_vpn["plan"], active_vpn["plan"])
        client_id = active_vpn["xui_client_id"]
        email = active_vpn["xui_email"] or f"user_{user.id}"
        host = config.XUI_HOST or "38.135.55.114"
        port = config.XUI_PORT or 47506
        vless_link = f"vless://{client_id}@{host}:{port}?type=tcp&security=tls&fp=chrome#{email}"
        vpn_status = (
            f"{EMOJI_CHECK} <b>Активен ({plan_label})</b>\n\n"
            f"{EMOJI_LINK} <b>Ваша ссылка подключения:</b>\n"
            f"<code>{vless_link}</code>"
        )
    elif active_vpn:
        plan_label = PLAN_NAMES.get(active_vpn["plan"], active_vpn["plan"])
        vpn_status = f"{EMOJI_CHECK} <b>Активен ({plan_label})</b>"
    else:
        vpn_status = f"{EMOJI_CROSS} <b>Нет активной подписки</b>"

    text = (
        f"{EMOJI_USER} <b>Личный кабинет</b>\n\n"
        f"{EMOJI_USER} <b>Пользователь:</b> {html.escape(user.full_name)}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n\n"
        f"{EMOJI_FOLDER} <b>Статус VPN:</b>\n{vpn_status}\n\n"
        f"{EMOJI_FRIENDS} <b>Приглашено друзей:</b> {referral_count}\n"
        f"🎁 <b>Бонусные дни:</b> {bonus_days} дн.\n"
        f"{EMOJI_BRIEFCASE} <b>Партнёрский баланс:</b> {partner_earnings}₽\n"
    )
    await send_or_edit_banner(call, "main_menu.jpg", text, reply_markup=profile_menu(bonus_days=bonus_days))

# ── Реферальная программа («5 дней за друга») ────────────────────────────────
@router.callback_query(F.data == "referral")
async def show_referral(call: CallbackQuery):
    user = call.from_user
    ref_link = f"https://t.me/{config.BOT_USERNAME}?start=ref{user.id}"
    first_name = html.escape(user.first_name)

    text = (
        f"👋 {first_name}, Вы знали, что можете приглашать друзей в наш сервис "
        f"и каждый из вас получит <b>5 дней в подарок</b>?\n\n"
        f"{EMOJI_LINK} <b>Ваша пригласительная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        "Отправьте эту ссылку друзьям — как только друг перейдёт по ней и запустит бота, "
        "вы оба получите по +5 бонусных дней!"
    )
    await send_or_edit_banner(call, "main_menu.jpg", text, reply_markup=referral_menu(ref_link))

# ── Партнёрская программа («Заработать с нами») ──────────────────────────────
@router.callback_query(F.data == "partner")
async def show_partner(call: CallbackQuery):
    user = call.from_user
    profile = await db.get_user_profile(user.id)
    partner_link = profile["partner_link"] if profile and profile["partner_link"] else None
    earnings = profile["partner_earnings"] if profile else 0

    link_text = f"<code>{partner_link}</code>" if partner_link else "<i>(ссылка ещё не создана)</i>"

    text = (
        f"{EMOJI_BRIEFCASE} <b>Партнёрская программа GHOST VPN</b>\n\n"
        "Если у Вас есть возможность привлекать клиентов, то мы предлагаем взаимовыгодное партнерство.\n\n"
        f"Нажмите на кнопку {EMOJI_LINK} <b>Создать партнерскую ссылку</b>, и бот автоматически сгенерирует для Вас уникальную ссылку для заработка.\n\n"
        f"Вы будете получать <b>{config.PARTNER_PERCENT}%</b> с каждой продажи и продления ключей.\n"
        f"Минимальная сумма для вывода — от <b>{config.PARTNER_MIN_WITHDRAWAL}₽</b>.\n\n"
        f"{EMOJI_COIN} <b>Ваш заработок:</b> {earnings}₽\n"
        f"{EMOJI_LINK} <b>Партнёрская ссылка:</b>\n{link_text}\n\n"
        f"{EMOJI_PHONE} Для вывода средств пишите в поддержку: @{config.SUPPORT_USERNAME}"
    )
    await send_or_edit_banner(call, "main_menu.jpg", text, reply_markup=partner_menu(has_link=bool(partner_link)))

@router.callback_query(F.data == "create_partner_link")
async def create_partner_link_handler(call: CallbackQuery):
    user = call.from_user
    link = f"https://t.me/{config.BOT_USERNAME}?start=partner{user.id}"
    await db.set_partner_link(user.id, link)
    await call.answer("✅ Партнёрская ссылка успешно создана!", show_alert=True)
    await show_partner(call)

# ── Пробный день («Получить пробные 1 день») ─────────────────────────────────
@router.callback_query(F.data == "trial")
async def get_trial_handler(call: CallbackQuery):
    user = call.from_user
    can_use = await db.use_trial(user.id)
    if not can_use:
        await call.answer("⚠️ Вы уже использовали свой пробный период!", show_alert=True)
        return

    await call.answer("⏳ Создаём пробный доступ...")
    try:
        result = await xui_client.add_client(user.id, plan="trial", custom_days=config.TRIAL_DAYS)
        order_id = await db.create_order(
            user_id=user.id,
            username=user.username or "",
            full_name=user.full_name,
            plan="trial",
            price=0,
        )
        await db.update_order_status(
            order_id,
            status="approved",
            xui_client_id=result["client_id"],
            xui_email=result["email"]
        )

        user_text = (
            f"🎉 {EMOJI_FLASH} <b>Ваш пробный доступ на 1 день активирован!</b>\n\n"
            f"⏳ Срок: <b>1 день</b>\n\n"
            f"{EMOJI_GEAR} <b>Ваша ссылка подключения:</b>\n"
            f"<code>{result['link']}</code>\n\n"
            "📲 <b>Как подключиться:</b>\n"
            "1. Скопируйте ссылку выше\n"
            "2. Вставьте в приложение (<b>v2rayNG</b> / <b>Hiddify</b> / <b>Streisand</b> / <b>Happ</b> / <b>V2Box</b>)\n"
            "3. Нажмите кнопку подключения!\n\n"
            f"{EMOJI_PHONE} По вопросам: @{config.SUPPORT_USERNAME}"
        )
        await send_or_edit_banner(call, "success_vpn.jpg", user_text, reply_markup=back_to_profile())
    except Exception as e:
        await call.message.answer(f"{EMOJI_CROSS} Ошибка создания пробного доступа: {e}")

# ── Активация накопленных бонусных дней ───────────────────────────────────────
@router.callback_query(F.data == "activate_bonus")
async def activate_bonus_handler(call: CallbackQuery):
    user = call.from_user
    days = await db.use_bonus_days(user.id)
    if days <= 0:
        await call.answer("⚠️ У вас нет доступных бонусных дней.", show_alert=True)
        return

    await call.answer(f"⏳ Активируем {days} бонусных дней...")
    try:
        result = await xui_client.add_client(user.id, plan="bonus", custom_days=days)
        order_id = await db.create_order(
            user_id=user.id,
            username=user.username or "",
            full_name=user.full_name,
            plan=f"bonus_{days}",
            price=0,
        )
        await db.update_order_status(
            order_id,
            status="approved",
            xui_client_id=result["client_id"],
            xui_email=result["email"]
        )

        user_text = (
            f"🎉 {EMOJI_FLASH} <b>Бонусные дни успешно активированы!</b>\n\n"
            f"⏳ Срок: <b>{days} дней</b>\n\n"
            f"{EMOJI_GEAR} <b>Ваша ссылка подключения:</b>\n"
            f"<code>{result['link']}</code>\n\n"
            "📲 Вставьте ссылку в ваше VPN-приложение и пользуйтесь бесплатно!"
        )
        await send_or_edit_banner(call, "success_vpn.jpg", user_text, reply_markup=back_to_profile())
    except Exception as e:
        await call.message.answer(f"{EMOJI_CROSS} Ошибка активации бонусов: {e}")

# ── Подарить подписку («Подарить подписку») ──────────────────────────────────
@router.callback_query(F.data == "gift")
async def show_gift_tariffs(call: CallbackQuery):
    prices = await db.get_prices()
    text = (
        f"🎁 {EMOJI_SHOP} <b>Подарить подписку GHOST VPN</b>\n\n"
        "Выберите тариф подписки, который хотите подарить другу:"
    )
    await send_or_edit_banner(call, "buy_tariffs.jpg", text, reply_markup=gift_tariffs_menu(prices))

@router.callback_query(F.data.startswith("giftplan_"))
async def select_gift_plan(call: CallbackQuery, state: FSMContext):
    plan = call.data.replace("giftplan_", "")
    plan_name = PLAN_NAMES.get(plan, plan)

    prices = await db.get_prices()
    price_key = PLAN_PRICE_KEYS.get(plan)
    price = prices.get(price_key, 0)

    await state.update_data(plan=plan, price=price, plan_name=plan_name, is_gift=True)
    await state.set_state(OrderStates.waiting_gift_recipient)

    text = (
        f"🎁 Вы выбрали подарок: <b>{html.escape(plan_name)}</b> — <b>{price}₽</b>\n\n"
        f"{EMOJI_USER} Введите <b>@username</b> или <b>Telegram ID</b> получателя подарка:\n"
        "<i>(например: @username или 123456789)</i>"
    )
    await call.message.answer(text, parse_mode="HTML")

@router.message(OrderStates.waiting_gift_recipient)
async def process_gift_recipient(message: Message, state: FSMContext):
    recipient_text = message.text.strip()
    data = await state.get_data()
    plan_name = data["plan_name"]
    price = data["price"]

    gift_to_user_id = None
    gift_to_username = None

    if recipient_text.isdigit():
        gift_to_user_id = int(recipient_text)
    else:
        gift_to_username = recipient_text.lstrip("@")
        found_user = await db.find_user_by_username(gift_to_username)
        if found_user:
            gift_to_user_id = found_user["user_id"]

    await state.update_data(
        gift_to_user_id=gift_to_user_id,
        gift_to_username=gift_to_username or recipient_text
    )
    await state.set_state(OrderStates.waiting_gift_screenshot)

    text = (
        f"🎁 <b>Оформление подарка для:</b> {html.escape(recipient_text)}\n"
        f"{EMOJI_FOLDER} Тариф: <b>{html.escape(plan_name)}</b> — <b>{price}₽</b>\n\n"
        f"{EMOJI_GEAR} <b>Реквизиты для оплаты:</b>\n"
        f"<code>{html.escape(config.PAYMENT_DETAILS)}</code> (Обязательно OZON Банк / СБП)\n\n"
        f"{EMOJI_CHAT} <b>После оплаты отправьте скриншот чека в этот чат.</b>\n\n"
        "После подтверждения оплаты ключ будет создан и выдан!"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=back_to_profile())

# ── Раздел Помощь ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "help_menu")
async def show_help_menu(call: CallbackQuery):
    text = (
        f"{EMOJI_PHONE} <b>Центр помощи GHOST VPN</b>\n\n"
        "❓ <b>Как подключить VPN?</b>\n"
        "1. Скачайте приложение:\n"
        "• iOS: <b>Streisand</b>, <b>Happ</b>, <b>V2Box</b>\n"
        "• Android: <b>v2rayNG</b>, <b>Happ</b>\n"
        "• Windows / Mac: <b>Hiddify</b>, <b>Nekoray</b>\n"
        "2. Скопируйте ключ подключения из бота\n"
        "3. Вставьте ключ в приложение и нажмите Подключить.\n\n"
        f"{EMOJI_CHAT} Нужна помощь оператора? Пишите: @{config.SUPPORT_USERNAME}"
    )
    await send_or_edit_banner(call, "main_menu.jpg", text, reply_markup=back_to_profile())

# ── Приём скриншота (обычный заказ и подарок) ──────────────────────────────────
@router.message(OrderStates.waiting_screenshot, F.photo)
@router.message(OrderStates.waiting_gift_screenshot, F.photo)
async def receive_screenshot(message: Message, state: FSMContext, bot=None):
    data = await state.get_data()
    plan = data["plan"]
    price = data["price"]
    plan_name = data["plan_name"]
    is_gift = data.get("is_gift", False)
    gift_to_user_id = data.get("gift_to_user_id")
    gift_to_username = data.get("gift_to_username")

    user = message.from_user
    file_id = message.photo[-1].file_id

    order_id = await db.create_order(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name,
        plan=plan,
        price=price,
        gift_to_user_id=gift_to_user_id,
        gift_to_username=gift_to_username,
    )
    await db.update_order_screenshot(order_id, file_id)
    await state.clear()

    # Начисление партнёрских процентов если пользователя привёл партнёр
    user_prof = await db.get_user_profile(user.id)
    if user_prof and user_prof["partner_referrer_id"] and price > 0:
        partner_id = user_prof["partner_referrer_id"]
        earnings = (price * config.PARTNER_PERCENT) // 100
        await db.add_partner_earnings(partner_id, earnings)
        if bot:
            try:
                await bot.send_message(
                    chat_id=partner_id,
                    text=(
                        f"💵 {EMOJI_COIN} <b>Партнёрское начисление!</b>\n\n"
                        f"Ваш реферал совершил оплату на сумму {price}₽.\n"
                        f"Вам начислено <b>+{earnings}₽</b> ({config.PARTNER_PERCENT}%)."
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

    gift_note = f"\n🎁 <b>Подарок для:</b> @{html.escape(str(gift_to_username or gift_to_user_id))}" if is_gift else ""

    await message.answer(
        f"{EMOJI_CHECK} {EMOJI_BOT} <b>Ваш заказ #{order_id} получен!</b>{gift_note}\n"
        f"{EMOJI_CHAT} Ожидайте подтверждения от администратора. Обычно это занимает до 30 минут.",
        parse_mode="HTML"
    )

    if bot:
        username_str = f"@{html.escape(user.username)}" if user.username else "без username"
        full_name_str = html.escape(user.full_name) if user.full_name else "Без имени"
        
        admin_text = (
            f"{EMOJI_FOLDER} <b>Заказ #{order_id}</b>{' [ПОДАРОК 🎁]' if is_gift else ''}\n"
            f"{EMOJI_USER} Покупатель: {full_name_str} ({username_str})\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📅 Тариф: {html.escape(plan_name)}\n"
            f"{EMOJI_COIN} Сумма: {price}₽\n"
            f"{gift_note}\n\n"
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
@router.message(OrderStates.waiting_gift_screenshot)
async def wrong_screenshot(message: Message):
    await message.answer("📸 Пожалуйста, отправьте именно <b>фото</b> (скриншот чека).", parse_mode="HTML")
