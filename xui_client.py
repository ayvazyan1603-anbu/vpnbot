import aiohttp
import uuid
import time
import ssl
import config

# Inbound ID на вашем сервере — уточните у заказчика или возьмём первый доступный
DEFAULT_INBOUND_ID = 1

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def _headers():
    return {
        "Authorization": f"Bearer {config.XUI_API_TOKEN}",
        "Content-Type": "application/json",
    }


def _plan_days(plan: str) -> int:
    mapping = {
        "1_month": 30,
        "3_months": 90,
        "6_months": 180,
        "12_months": 365,
    }
    return mapping.get(plan, 30)


async def add_client(user_id: int, plan: str) -> dict:
    """
    Создаёт нового клиента в 3x-ui и возвращает данные подключения.
    """
    days = _plan_days(plan)
    expire_ms = int((time.time() + days * 86400) * 1000)

    client_id = str(uuid.uuid4())
    email = f"user_{user_id}_{int(time.time())}"

    payload = {
        "id": DEFAULT_INBOUND_ID,
        "settings": {
            "clients": [
                {
                    "id": client_id,
                    "email": email,
                    "limitIp": 1,
                    "totalGB": 0,
                    "expiryTime": expire_ms,
                    "enable": True,
                    "tgId": str(user_id),
                    "subId": "",
                }
            ]
        },
    }

    url = f"{config.XUI_URL}/panel/api/inbounds/addClient"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=payload, headers=_headers(), ssl=ssl_ctx, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            data = await resp.json()
            if not data.get("success"):
                raise Exception(f"3x-ui error: {data.get('msg', 'unknown error')}")

    # Получаем данные inbound чтобы собрать ссылку подключения
    conn_link = await get_client_link(client_id, email)

    return {
        "client_id": client_id,
        "email": email,
        "link": conn_link,
        "expire_days": days,
    }


async def get_client_link(client_id: str, email: str) -> str:
    """
    Получает inbound и формирует ссылку vless:// для клиента.
    """
    url = f"{config.XUI_URL}/panel/api/inbounds/get/{DEFAULT_INBOUND_ID}"

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url, headers=_headers(), ssl=ssl_ctx, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            data = await resp.json()

    if not data.get("success"):
        return "Ошибка получения ссылки. Обратитесь в поддержку."

    inbound = data["obj"]
    protocol = inbound.get("protocol", "vless")
    port = inbound.get("port", config.XUI_PORT)
    host = config.XUI_HOST

    # Формируем стандартную ссылку vless
    link = (
        f"{protocol}://{client_id}@{host}:{port}"
        f"?type=tcp&security=tls&fp=chrome"
        f"#{email}"
    )
    return link


async def disable_client(email: str):
    """Отключает клиента (при отмене заказа)."""
    url = f"{config.XUI_URL}/panel/api/inbounds/{DEFAULT_INBOUND_ID}/delClient/{email}"
    async with aiohttp.ClientSession() as session:
        await session.post(url, headers=_headers(), ssl=ssl_ctx)
