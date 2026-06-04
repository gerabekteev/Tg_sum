import asyncio
import logging
import sys
from telethon import TelegramClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from bot import setup_bot, process_and_send_summary

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.BASE_DIR / "app.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Запуск Telegram-Саммаризатора...")

    # 1. Валидация конфигурации .env
    errors = config.validate_config()
    if errors:
        logger.error("Ошибки конфигурации .env. Скрипт не может быть запущен:")
        for err in errors:
            print(f"❌ {err}")
        print("\nПожалуйста, настройте файл .env согласно инструкции в README.md и запустите скрипт снова.")
        sys.exit(1)

    # 2. Инициализация клиентов
    logger.info("Инициализация клиентов Telegram...")
    
    # Клиент юзербота
    user_client = TelegramClient(
        config.USER_SESSION_PATH, 
        config.API_ID, 
        config.API_HASH
    )
    
    # Клиент управляющего бота
    bot_client = TelegramClient(
        config.BOT_SESSION_PATH, 
        config.API_ID, 
        config.API_HASH
    )

    try:
        # 3. Авторизация юзербота
        # Если запускается впервые, спросит телефон и код в консоли
        logger.info("Авторизация юзербота (может потребоваться ввод кода в консоли)...")
        await user_client.start(phone=lambda: config.TELEGRAM_PHONE)
        logger.info("Юзербот успешно авторизован!")

        # 4. Авторизация бота
        logger.info("Авторизация управляющего бота по токену...")
        await bot_client.start(bot_token=config.BOT_TOKEN)
        logger.info("Управляющий бот успешно авторизован!")

    except Exception as e:
        logger.error(f"Не удалось авторизовать клиентов Telegram: {e}")
        logger.error("Пожалуйста, убедитесь, что API_ID, API_HASH и BOT_TOKEN указаны верно.")
        sys.exit(1)

    # 5. Инициализация планировщика для авто-сбора сообщений
    scheduler = AsyncIOScheduler()
    
    async def auto_fetch_job():
        logger.info("Старт фонового авто-сбора сообщений...")
        await process_and_send_summary(
            bot_client=bot_client,
            user_client=user_client,
            admin_id=config.ADMIN_ID,
            since_last=True
        )

    # Добавляем задачу (период настраивается в часах из config)
    period = config.get_period_hours()
    scheduler.add_job(
        auto_fetch_job, 
        'interval', 
        hours=period,
        id="auto_fetch_messages"
    )
    scheduler.start()
    logger.info(f"Планировщик запущен. Сбор новых сообщений каждые {period} ч.")
    logger.info(f"Целевой чат: {config.get_target_chat()}")

    # 6. Регистрация обработчиков управляющего бота
    setup_bot(bot_client, user_client, scheduler=scheduler)
    logger.info("Интерфейс управления бота настроен.")
    logger.info("Отправьте /start вашему боту в Telegram для начала работы.")


    # 7. Поддержание работы клиентов в бесконечном цикле событий
    logger.info("Приложение готово к работе и ожидает событий.")
    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected()
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Приложение остановлено пользователем.")
