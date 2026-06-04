import datetime
import json
import logging
import os
from telethon import TelegramClient, events, Button
from telethon.tl.types import PeerChannel, PeerChat, PeerUser
import config
import parser
import summarizer

logger = logging.getLogger(__name__)

# Файл для хранения состояния (последний прочитанный ID сообщения и время)
STATE_FILE = config.SESSIONS_DIR / "state.json"

# Хранилище состояний диалогов (для обработки ввода настроек)
# Формат: {user_id: {"action": "awaiting_chat_id"}}
_user_states = {}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Не удалось прочитать state.json: {e}")
    return {"last_message_id": 0, "last_run_timestamp": None}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Не удалось сохранить state.json: {e}")


# ─── Клавиатуры ───

def get_main_keyboard():
    """Возвращает Reply-клавиатуру главного меню."""
    return [
        [
            Button.text("📥 За 1 час", resize=True),
            Button.text("📥 За 4 часа"),
            Button.text("📥 За 24 часа")
        ],
        [
            Button.text("🔄 Собрать новые"),
            Button.text("⚙️ Настройки")
        ]
    ]

def get_settings_keyboard():
    """Возвращает Reply-клавиатуру меню настроек."""
    return [
        [
            Button.text("📝 Изменить чат", resize=True),
            Button.text("⏱ Изменить период")
        ],
        [
            Button.text("📋 Текущие настройки"),
            Button.text("🔙 Назад в меню")
        ]
    ]


# ─── Основная функция сбора ───

async def process_and_send_summary(
    bot_client: TelegramClient,
    user_client: TelegramClient,
    admin_id: int,
    hours: int = None,
    since_last: bool = False
):
    """
    Основная функция сбора истории и отправки файла пользователю.
    """
    chat_target = config.get_target_chat()
    if not chat_target:
        await bot_client.send_message(
            admin_id,
            "❌ Целевой чат не указан.\n\nНажмите **⚙️ Настройки** → **📝 Изменить чат** для настройки.",
            buttons=get_main_keyboard()
        )
        return

    await bot_client.send_message(
        admin_id, 
        f"⏳ Начинаю сбор сообщений из `{chat_target}`...",
        buttons=Button.clear()
    )

    state = load_state()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    min_id = None

    # Определяем временной интервал
    if since_last:
        # Сбор с последнего запуска
        last_run = state.get("last_run_timestamp")
        min_id = state.get("last_message_id")
        if last_run:
            try:
                start_time = datetime.datetime.fromisoformat(last_run)
            except Exception:
                start_time = now_utc - datetime.timedelta(hours=config.get_period_hours())
        else:
            start_time = now_utc - datetime.timedelta(hours=config.get_period_hours())
        
        # Переводим в часовой пояс пользователя для корректного отображения
        local_start_time = start_time.astimezone(config.TIMEZONE)
        period_str = f"с момента последнего запуска ({local_start_time.strftime('%d.%m %H:%M')})"
    else:
        # Сбор за фиксированные часы
        start_time = now_utc - datetime.timedelta(hours=hours)
        period_str = f"за последние {hours} ч."

    try:
        # Вызов парсера
        msgs, formatted_text = await parser.fetch_messages_for_period(
            client=user_client,
            chat_peer=chat_target,
            start_time=start_time if not min_id else None,
            end_time=now_utc,
            min_id=min_id if min_id else None
        )

        if not msgs:
            await bot_client.send_message(
                admin_id,
                f"ℹ️ В чате `{chat_target}` не найдено новых текстовых сообщений {period_str}.",
                buttons=get_main_keyboard()
            )
            # Все равно обновляем время последнего запуска
            state["last_run_timestamp"] = now_utc.isoformat()
            save_state(state)
            return

        # Имя файла для сохранения
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_chat_name = "".join(c for c in str(chat_target) if c.isalnum() or c in ('@', '_', '-'))
        filename = f"messages_{safe_chat_name}_{timestamp_str}.txt"
        file_path = config.DUMPS_DIR / filename

        # Сохраняем локально
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(formatted_text)

        # Обновляем состояние
        max_id = max(m["id"] for m in msgs)
        state["last_message_id"] = max_id
        state["last_run_timestamp"] = now_utc.isoformat()
        save_state(state)

        # Отправляем файл пользователю
        caption = (
            f"✅ **Сбор успешно завершен!**\n\n"
            f"📋 **Чат:** `{chat_target}`\n"
            f"⏱ **Период:** {period_str}\n"
            f"💬 **Найдено сообщений:** {len(msgs)}\n"
            f"📁 **Файл сохранен:** `dumps/{filename}`"
        )
        
        await bot_client.send_file(
            admin_id,
            file=str(file_path),
            caption=caption,
            buttons=get_main_keyboard()
        )

        # Отправляем статусное сообщение
        status_msg = await bot_client.send_message(
            admin_id,
            "⏳ **Генерирую ИИ-саммари...**"
        )

        # Вызов ИИ для саммаризации
        try:
            summary = await summarizer.summarize_messages(formatted_text)
            
            # Удаляем статусное сообщение
            try:
                await status_msg.delete()
            except Exception:
                pass
            
            # Отправляем саммари пользователю
            header = f"📊 **ИИ-Саммари переписки ({period_str}):**\n\n"
            full_msg = f"{header}{summary}"
            
            # Телеграм имеет ограничение на длину сообщения в 4096 символов
            if len(full_msg) > 4096:
                # Разбиваем на части
                for i in range(0, len(full_msg), 4090):
                    part = full_msg[i:i+4090]
                    await bot_client.send_message(admin_id, part)
            else:
                await bot_client.send_message(admin_id, full_msg)
            
        except Exception as ai_err:
            logger.error(f"Не удалось сгенерировать саммари: {ai_err}")
            # Удаляем статусное сообщение при ошибке
            try:
                await status_msg.delete()
            except Exception:
                pass
            await bot_client.send_message(
                admin_id,
                f"⚠️ **Не удалось сгенерировать ИИ-саммари:**\n`{str(ai_err)}`"
            )

    except Exception as e:
        logger.exception("Ошибка во время сбора сообщений")
        await bot_client.send_message(
            admin_id,
            f"❌ Произошла ошибка при сборе:\n`{str(e)}`",
            buttons=get_main_keyboard()
        )


# ─── Настройка обработчиков бота ───

def setup_bot(bot_client: TelegramClient, user_client: TelegramClient, scheduler=None):
    """Настройка обработчиков событий для управляющего бота."""

    # Декоратор для проверки того, что пишет именно администратор
    def admin_only(func):
        async def wrapper(event):
            sender_id = event.sender_id
            if sender_id != config.ADMIN_ID:
                logger.warning(f"Попытка доступа от постороннего ID: {sender_id}")
                return
            return await func(event)
        return wrapper

    @bot_client.on(events.NewMessage(pattern="/start"))
    @admin_only
    async def start_handler(event):
        _user_states.pop(event.sender_id, None)  # Сбрасываем состояние
        welcome_text = (
            "👋 **Привет! Я бот управления Telegram-Саммаризатором.**\n\n"
            "Я помогу тебе собирать сообщения из целевого чата.\n"
            "Используй кнопки меню ниже для управления."
        )
        await event.respond(welcome_text, buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage)
    @admin_only
    async def message_handler(event):
        text = event.raw_text
        user_id = event.sender_id

        # Пропускаем команду /start (обработана выше)
        if text == "/start":
            return

        # ─── Обработка ввода настроек (если ожидаем ответ) ───
        user_state = _user_states.get(user_id)
        if user_state:
            action = user_state.get("action")

            if action == "awaiting_chat_id":
                _user_states.pop(user_id, None)
                new_chat = text.strip()

                if not new_chat:
                    await event.respond(
                        "❌ Пустое значение. Попробуйте снова.",
                        buttons=get_settings_keyboard()
                    )
                    return

                # Сохраняем новый чат
                config.set_target_chat(new_chat)
                await event.respond(
                    f"✅ **Целевой чат обновлен!**\n\n"
                    f"Новое значение: `{new_chat}`\n\n"
                    f"Попробуйте собрать сообщения, чтобы проверить подключение.",
                    buttons=get_main_keyboard()
                )
                return

            elif action == "awaiting_period":
                _user_states.pop(user_id, None)
                try:
                    new_period = int(text.strip())
                    if new_period < 1 or new_period > 168:
                        raise ValueError("Период должен быть от 1 до 168 часов")
                except ValueError as e:
                    await event.respond(
                        f"❌ Некорректное значение: {e}\n"
                        f"Введите целое число от 1 до 168.",
                        buttons=get_settings_keyboard()
                    )
                    return

                config.set_period_hours(new_period)

                # Динамически перенастраиваем задачу в планировщике, если он передан
                if scheduler:
                    try:
                        scheduler.reschedule_job(
                            "auto_fetch_messages", 
                            trigger='interval', 
                            hours=new_period
                        )
                        reschedule_status = "✅ Изменения применены мгновенно в работающем планировщике!"
                    except Exception as scheduler_err:
                        logger.error(f"Не удалось перенастроить задачу в планировщике: {scheduler_err}")
                        reschedule_status = "⚠️ Изменение вступит в силу при следующем перезапуске приложения."
                else:
                    reschedule_status = "⚠️ Изменение вступит в силу при следующем перезапуске приложения."

                await event.respond(
                    f"✅ **Период автосбора обновлен!**\n\n"
                    f"Новое значение: **{new_period} ч.**\n\n"
                    f"{reschedule_status}",
                    buttons=get_settings_keyboard()
                )
                return

        # ─── Главное меню ───
        if text == "📥 За 1 час":
            await process_and_send_summary(bot_client, user_client, config.ADMIN_ID, hours=1)
        elif text == "📥 За 4 часа":
            await process_and_send_summary(bot_client, user_client, config.ADMIN_ID, hours=4)
        elif text == "📥 За 24 часа":
            await process_and_send_summary(bot_client, user_client, config.ADMIN_ID, hours=24)
        elif text == "🔄 Собрать новые":
            await process_and_send_summary(bot_client, user_client, config.ADMIN_ID, since_last=True)

        # ─── Меню настроек ───
        elif text == "⚙️ Настройки":
            _user_states.pop(user_id, None)
            await event.respond(
                "⚙️ **Меню настроек**\n\n"
                "Выберите, что хотите изменить:",
                buttons=get_settings_keyboard()
            )

        elif text == "📝 Изменить чат":
            current_chat = config.get_target_chat()
            _user_states[user_id] = {"action": "awaiting_chat_id"}
            await event.respond(
                f"📝 **Изменение целевого чата**\n\n"
                f"Текущий чат: `{current_chat or 'не задан'}`\n\n"
                f"Отправьте новый ID группы или @username.\n\n"
                f"**Форматы:**\n"
                f"• `@group_username` — юзернейм группы\n"
                f"• `-1001234567890` — ID супергруппы (с префиксом -100)\n"
                f"• `1234567890` — ID без префикса (бот подберет формат автоматически)\n\n"
                f"Отправьте /start для отмены.",
                buttons=Button.clear()
            )

        elif text == "⏱ Изменить период":
            current_period = config.get_period_hours()
            _user_states[user_id] = {"action": "awaiting_period"}
            await event.respond(
                f"⏱ **Изменение периода автосбора**\n\n"
                f"Текущий период: **{current_period} ч.**\n\n"
                f"Отправьте новый период в часах (от 1 до 168).\n"
                f"Например: `2` для сбора каждые 2 часа.\n\n"
                f"Отправьте /start для отмены.",
                buttons=Button.clear()
            )

        elif text == "📋 Текущие настройки":
            state = load_state()
            errors = config.validate_config()
            current_chat = config.get_target_chat()
            current_period = config.get_period_hours()

            status_msg = (
                "📋 **Текущие настройки системы:**\n\n"
                f"🔹 **Целевой чат:** `{current_chat or 'не задан'}`\n"
                f"🔹 **Ваш Telegram ID:** `{config.ADMIN_ID}`\n"
                f"🔹 **Период автосбора:** {current_period} ч.\n"
                f"🔹 **Последнее сообщение ID:** {state.get('last_message_id', 0)}\n"
                f"🔹 **Последний запуск:** {state.get('last_run_timestamp') or 'Никогда'}\n\n"
            )
            
            if errors:
                status_msg += "⚠️ **Проблемы в настройках .env:**\n"
                for err in errors:
                    status_msg += f"• {err}\n"
            else:
                status_msg += "✅ Все базовые настройки .env заполнены корректно."
                
            await event.respond(status_msg, buttons=get_settings_keyboard())

        elif text == "🔙 Назад в меню":
            _user_states.pop(user_id, None)
            await event.respond(
                "🏠 **Главное меню**",
                buttons=get_main_keyboard()
            )
