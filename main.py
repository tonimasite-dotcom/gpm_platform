# from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

if (
    __name__ == '__main__'
    and os.getenv('GPM_ENABLE_LEGACY_BOT', '').strip().lower() != 'true'
):
    raise SystemExit(
        'Legacy Telegram bot is disabled by default. '
        'Complete its security and personal-data review before enabling it.'
    )

from aiogram import Dispatcher
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.utils.executor import start_webhook, start_polling

from app.db import models
from app.db.database import init_db, close_db
from app.dependencies import CHAT_IDS, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT, bot, WEBHOOK_DOMAIN
from app.handlers import dp
from app.services.notify_admins import notify_wakeup_bot
from app.services.set_bot_commands import set_default_commands
from logs.log_info import logger

MAX_CALLBACKS = 50  
processed_callbacks = set()

class UsernameMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message, data):
        if message.chat.id in CHAT_IDS.values():
            logger.debug(f'chat.id {message.chat.id} user.id {message.from_user.id}')
            raise CancelHandler()
        
        if message.text and message.text.startswith('/start'):
            parts = message.text.split()
            if len(parts) > 1:
                ref_param = parts[1]
                logger.info(f"User {message.from_user.id} started with ref: {ref_param}")
                
                try:
                    await models.Referral.increment_counter(ref_param)
                    
                    user = await models.User.get_user(message.from_user.id)
                    if user:
                        if not user.referral_param:
                            user.referral_param = ref_param
                            await user.save()
                    else:
                        await models.User.create_user(
                            user_id=message.from_user.id,
                            username=message.from_user.username,
                            full_name=message.from_user.full_name,
                            referral_param=ref_param
                        )
                except Exception as e:
                    logger.error(f"Error processing referral: {e}")
        
        if message.from_user.username is None:
            await message.answer(
                text="Для работы с ботом необходимо установить «имя пользователя» в настройках телеграмма. Настройки → "
                     "Имя пользователя → Ввести имя пользователя → Нажать на галочку для подтверждения.\n"
                     "После добавления имени пользователя введите команду /start.")
            raise CancelHandler()

        user = await models.User.get_user(message.from_user.id)
        if user is None:
            return True

        elif message.text == '/stat':
            return True

        elif user.is_blocked:
            if user.block_reason == 'BotBlocked':
                user.is_blocked=False
                user.block_reason = None
                await user.save()
            else:
                await message.answer("Вы заблокированы")
                raise CancelHandler()

        elif user.username != message.from_user.username:
            old_username = user.username
            user.username = message.from_user.username
            await user.save()
            
            implementer = await models.Implementer.get_implementer(user)
            if implementer:
                if implementer.mark == 'Нет':
                    implementer.mark = ''
                implementer.mark += f'старый никнейм {old_username}\n'
                await implementer.save()
            return True


    async def on_pre_process_callback_query(self, callback_query, data):
        if callback_query.id in processed_callbacks:
            return  
        user = await models.User.get_user(callback_query.from_user.id)
        if user is None:
            return True

        elif user.is_blocked:
            if user.block_reason == 'BotBlocked':
                user.is_blocked=False
                user.block_reason = None
                await user.save()
            else:
                await callback_query.answer("Вы заблокированы", show_alert=True)
                raise CancelHandler()

        elif user.username != callback_query.from_user.username:
            user.username = callback_query.from_user.username
            await user.save()
            return True


async def on_startup(dp: Dispatcher):
    await set_default_commands(dp)
    await init_db()
    await notify_wakeup_bot(dp)
    await bot.set_webhook(WEBHOOK_DOMAIN + WEBHOOK_PATH)
    dp.setup_middleware(UsernameMiddleware())

    # scheduler = AsyncIOScheduler()
    # set_scheduled_jobs(scheduler)
    # scheduler.start()


async def on_shutdown(dp):
    await close_db()
    await dp.storage.close()
    await dp.storage.wait_closed()
    await bot.session.close()
    await bot.delete_webhook()


# def set_scheduled_jobs(scheduler, *args, **kwargs):
#     scheduler.add_job(func_name, "interval", seconds=10)


if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
