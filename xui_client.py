import aiohttp
import uuid
import time
import ssl
import config

# ID вашего инбаунда в панели 3x-ui
DEFAULT_INBOUND_ID = 1

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def _base_url() -> str:
    """Корневой URL без пути панели."""
    if not config.XUI_URL:
        return ""
    return config.XUI_URL.rstrip("/")


def _headers() -> dict:
    """Заголовки для Bearer-аутентификации через API-токен."""
    return {
        "Authorization": f"Bearer {config.XUI_API_TOKEN}",
        "Content-Type": "application/json",
    }


def _plan_days(plan: str | int) -> int:
    if isinstance(plan, int):
        return plan
    if str(plan).startswith("bonus_"):
        try:
            return int(str(plan).split("_")[1])
        except Exception:
            return 5
    return {
        "trial": config.TRIAL_DAYS,
        "1_month": 30,
        "3_months": 90,
        "6_months": 180,
        "12_months": 365,
    }.get(plan, 30)


async def add_client(user_id: int, plan: str | int, custom_days: int = None) -> dict:
    days = custom_days if custom_days is not None else _plan_days(plan)
    expire_ms = int((time.time() + days * 86400) * 1000)

    client_id = str(uuid.uuid4())
    email = f"user_{user_id}_{int(time.time())}"

    payload = {
        "client": {
            "id": client_id,
            "email": email,
            "totalGB": 0,
            "expiryTime": expire_ms,
            "tgId": user_id,
            "limitIp": 1,
            "enable": True,
        },
        "inboundIds": [DEFAULT_INBOUND_ID],
    }

    base = _base_url()
    if not base or not config.XUI_API_TOKEN:
        # Режим заглушки / без настроенного сервера
        link = (
            f"vless://{client_id}@{config.XUI_HOST or 'ghost.vpn'}:{config.XUI_PORT}"
            f"?type=tcp&security=tls&fp=chrome#{email}"
        )
        return {
            "client_id": client_id,
            "email": email,
            "link": link,
            "expire_days": days,
        }

    add_url = f"{base}/panel/api/clients/add"
    get_inbound_url = f"{base}/panel/api/inbounds/get/{DEFAULT_INBOUND_ID}"

    timeout = aiohttp.ClientTimeout(total=15)

    async with aiohttp.ClientSession(headers=_headers()) as session:
        async with session.post(add_url, json=payload, ssl=ssl_ctx, timeout=timeout) as resp:
            if resp.status == 401:
                raise Exception(
                    "Ошибка авторизации (401). Проверьте XUI_API_TOKEN в .env — "
                    "токен берётся в панели: Settings → Security → API Token."
                )
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Ошибка API (статус {resp.status}): {text[:300]}")

            data = await resp.json()
            if not data.get("success"):
                raise Exception(
                    f"Панель вернула ошибку: {data.get('msg', str(data))}"
                )

        async with session.get(get_inbound_url, ssl=ssl_ctx, timeout=timeout) as resp2:
            inbound_data = await resp2.json()

    if not inbound_data.get("success"):
        link = (
            f"Доступ создан, но ссылку не удалось сгенерировать автоматически. "
            f"Обратитесь в поддержку. Email: {email}"
        )
    else:
        inbound = inbound_data["obj"]
        protocol = inbound.get("protocol", "vless")
        port = inbound.get("port", config.XUI_PORT)
        host = config.XUI_HOST

        link = (
            f"{protocol}://{client_id}@{host}:{port}"
            f"?type=tcp&security=tls&fp=chrome"
            f"#{email}"
        )

    return {
        "client_id": client_id,
        "email": email,
        "link": link,
        "expire_days": days,
    }


async def disable_client(email: str):
    """Отключение/удаление клиента по email."""
    base = _base_url()
    if not base or not config.XUI_API_TOKEN:
        return
    url = f"{base}/panel/api/inbounds/{DEFAULT_INBOUND_ID}/delClient/{email}"
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(headers=_headers()) as session:
        await session.post(url, ssl=ssl_ctx, timeout=timeout)