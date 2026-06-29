from aiogram import types
from aiogram.utils import exceptions
from app.dependencies import dp, bot, ERRORS_ID
from logs.log_info import logger
import traceback  

@dp.errors_handler()
async def errors_handler(update: types.Update, exception: Exception):
    try:
        if isinstance(exception, exceptions.MessageNotModified):
            logger.warning("Сообщение не было изменено.")
            return True  

        # Формируем traceback
        tb_str = traceback.format_exc()  # Получаем traceback в виде строки
        logger.error(f"Ошибка: {exception}\nTraceback:\n{tb_str}")
        
        # Отправляем traceback в чат для ошибок
        #await bot.send_message(ERRORS_ID, f"Произошла ошибка: {exception}\nTraceback:\n{tb_str}")
        return True

    except Exception as e:
        # Если что-то пошло не так в самом обработчике ошибок
        logger.error(f"Ошибка в обработчике ошибок: {e}\nTraceback:\n{traceback.format_exc()}")
        return True