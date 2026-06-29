from aiogram import types
from app.dependencies import ADMINS


async def set_default_commands(dp):
    await dp.bot.set_my_commands([
        types.BotCommand("start", "Запустить бота"),
        # types.BotCommand("data", "Мои данные"),
        # types.BotCommand("orders", "Мои заказы"),
        # types.BotCommand("stat", "Статистика")
    ],
        scope=types.BotCommandScopeAllPrivateChats())

    # for chat_id in ADMINS:
    #     await dp.bot.set_my_commands([
    #         types.BotCommand("start", "Запустить бота"),
    #         types.BotCommand("admin", "Админка")
    #     ],
    #         scope=types.BotCommandScopeChat(chat_id=chat_id))
