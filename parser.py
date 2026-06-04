import datetime
import logging
from telethon import TelegramClient
from telethon.tl.types import User, PeerChannel

logger = logging.getLogger(__name__)


async def _resolve_chat_entity(client: TelegramClient, chat_peer: str):
    """
    Пытается найти чат-сущность в Telegram по ID или юзернейму.
    Автоматически обрабатывает различные форматы ID супергрупп.
    """
    # Если это юзернейм (@xxx) — используем как есть
    if chat_peer.startswith("@"):
        return await client.get_input_entity(chat_peer)

    # Пробуем преобразовать в число
    try:
        chat_id = int(chat_peer)
    except ValueError:
        # Не число и не юзернейм — пробуем как строку
        return await client.get_input_entity(chat_peer)

    # Стратегия 1: пробуем ID как есть
    try:
        return await client.get_input_entity(chat_id)
    except (ValueError, TypeError):
        pass

    # Стратегия 2: если ID отрицательный без префикса -100,
    # пробуем добавить префикс (для супергрупп и каналов)
    if chat_id < 0:
        chat_id_str = str(chat_id)
        if not chat_id_str.startswith("-100"):
            # Убираем минус, добавляем -100 префикс
            raw_id = abs(chat_id)
            full_id = int(f"-100{raw_id}")
            try:
                return await client.get_input_entity(full_id)
            except (ValueError, TypeError):
                pass

            # Стратегия 3: пробуем через PeerChannel
            try:
                return await client.get_input_entity(PeerChannel(raw_id))
            except (ValueError, TypeError):
                pass

    # Стратегия 4: для положительных чисел — пробуем как PeerChannel
    if chat_id > 0:
        try:
            return await client.get_input_entity(PeerChannel(chat_id))
        except (ValueError, TypeError):
            pass
        # И с -100 префиксом
        try:
            return await client.get_input_entity(int(f"-100{chat_id}"))
        except (ValueError, TypeError):
            pass

    raise ValueError(
        f"Не удалось найти чат '{chat_peer}'.\n"
        f"Подсказки:\n"
        f"• Для супергрупп используйте формат: -100XXXXXXXXXX\n"
        f"• Или перешлите сообщение из нужного чата этому боту\n"
        f"• Или используйте @username группы"
    )


async def fetch_messages_for_period(
    client: TelegramClient,
    chat_peer: str,
    start_time: datetime.datetime = None,
    end_time: datetime.datetime = None,
    min_id: int = None
):
    """
    Получает сообщения из чата за указанный период времени или с определенного ID (min_id).
    Возвращает список словарей с метаданными сообщений и отформатированный текст.
    """
    logger.info(f"Начало сбора сообщений из '{chat_peer}' (min_id={min_id}, start_time={start_time}, end_time={end_time or 'сейчас'})")
    
    # Импортируем config для доступа к TIMEZONE
    import config

    # Приводим входные даты к UTC, так как Telethon работает в UTC
    if start_time:
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=datetime.timezone.utc)
        else:
            start_time = start_time.astimezone(datetime.timezone.utc)
        
    if end_time:
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=datetime.timezone.utc)
        else:
            end_time = end_time.astimezone(datetime.timezone.utc)
    else:
        end_time = datetime.datetime.now(datetime.timezone.utc)

    collected_messages = []

    # Резолвим сущность чата с автоматическим подбором формата ID
    try:
        entity = await _resolve_chat_entity(client, chat_peer)
    except Exception as e:
        logger.error(f"Не удалось получить сущность чата {chat_peer}: {e}")
        raise ValueError(str(e))

    # Перебираем сообщения (по умолчанию от новых к старым)
    iter_args = {"limit": None}
    if min_id is not None:
        iter_args["min_id"] = int(min_id)

    async for message in client.iter_messages(entity, **iter_args):
        # Если сообщение старше начала периода — останавливаем сбор (только если start_time задан)
        if start_time and message.date < start_time:
            break
            
        # Если сообщение новее конца периода — пропускаем его (идем дальше в прошлое)
        if message.date > end_time:
            continue
            
        # Нам нужен только текст
        if not message.text:
            continue
            
        # Определяем имя отправителя без дополнительных запросов к Telegram API
        sender = message.sender
        if sender:
            if isinstance(sender, User):
                first = sender.first_name or ""
                last = sender.last_name or ""
                sender_name = f"{first} {last}".strip() or sender.username or f"ID {sender.id}"
            else:
                sender_name = getattr(sender, 'title', f"ID {sender.id}")
        else:
            sender_name = f"ID {message.sender_id or 'Unknown'}"
            
        collected_messages.append({
            "id": message.id,
            "date": message.date,
            "sender": sender_name,
            "text": message.text
        })

    # Переворачиваем список, чтобы сообщения шли в хронологическом порядке (от старых к новым)
    collected_messages.reverse()
    
    # Формируем структурированный текст
    formatted_text_lines = []
    for msg in collected_messages:
        # Переводим время в часовой пояс из конфигурации
        local_date = msg["date"].astimezone(config.TIMEZONE)
        date_str = local_date.strftime("%Y-%m-%d %H:%M:%S")
        formatted_text_lines.append(f"[{date_str}] [{msg['sender']}]: {msg['text']}\n")
        
    formatted_text = "".join(formatted_text_lines)
    
    logger.info(f"Собрано сообщений: {len(collected_messages)}")
    return collected_messages, formatted_text

