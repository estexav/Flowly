import asyncio
from typing import List, Dict, Any

import flet as ft
from services.firebase_service import add_transaction


def _cache_key(user_id: str) -> str:
    return f"cached_transactions:{user_id}"


def _queue_key(user_id: str) -> str:
    return f"pending_transactions:{user_id}"


async def get_cached_transactions(page: ft.Page, user_id: str) -> List[Dict[str, Any]]:
    data = await page.client_storage.get_async(_cache_key(user_id))
    return data or []


async def set_cached_transactions(page: ft.Page, user_id: str, transactions: List[Dict[str, Any]]):
    await page.client_storage.set_async(_cache_key(user_id), transactions)

def _recurring_key(user_id: str) -> str:
    return f"cached_recurrings:{user_id}"

async def get_cached_recurrings(page: ft.Page, user_id: str) -> List[Dict[str, Any]]:
    data = await page.client_storage.get_async(_recurring_key(user_id))
    return data or []

async def set_cached_recurrings(page: ft.Page, user_id: str, recurrings: List[Dict[str, Any]]):
    await page.client_storage.set_async(_recurring_key(user_id), recurrings)


async def add_pending_transaction(page: ft.Page, user_id: str, tx: Dict[str, Any]):
    queue = await page.client_storage.get_async(_queue_key(user_id)) or []
    queue.append(tx)
    await page.client_storage.set_async(_queue_key(user_id), queue)


async def get_pending_transactions(page: ft.Page, user_id: str) -> List[Dict[str, Any]]:
    return await page.client_storage.get_async(_queue_key(user_id)) or []


async def clear_pending_transactions(page: ft.Page, user_id: str):
    await page.client_storage.remove_async(_queue_key(user_id))


async def sync_pending_transactions(page: ft.Page, user_id: str) -> Dict[str, Any]:
    """
    Intenta enviar las transacciones pendientes a Firebase.
    Devuelve un resumen con cantidades sincronizadas y errores.
    """
    queue = await get_pending_transactions(page, user_id)
    if not queue:
        return {"synced": 0, "errors": []}

    loop = asyncio.get_event_loop()
    synced_count = 0
    errors: List[str] = []

    # Intentar subir cada transacción
    remaining: List[Dict[str, Any]] = []
    for tx in queue:
        try:
            result = await loop.run_in_executor(None, add_transaction, user_id, tx)
            if "error" in result:
                errors.append(result["error"])  # mantener en cola para intento posterior
                remaining.append(tx)
            else:
                synced_count += 1
        except Exception as e:
            errors.append(str(e))
            remaining.append(tx)

    # Actualizar cola
    if remaining:
        await page.client_storage.set_async(_queue_key(user_id), remaining)
    else:
        await clear_pending_transactions(page, user_id)

    return {"synced": synced_count, "errors": errors}

