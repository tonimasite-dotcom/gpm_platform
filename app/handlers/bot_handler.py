from aiogram import types

from app.dependencies import dp


@dp.my_chat_member_handler()
async def admin_promoted(event: types.ChatMemberUpdated):
    old = event.old_chat_member
    new = event.new_chat_member

    if event.chat.type == 'private':
        if old.status == 'member' and new.status == 'kicked':
            # Блокировка бота пользователем
            return

        elif old.status == 'kicked' and new.status == 'member':
            # Разблокировка бота пользователем
            return

    if not old.is_chat_admin() and new.is_chat_admin():
        if event.chat.type in ['group', 'supergroup']:
            # Добавление бота в администраторы чата
            pass
        elif event.chat.type == 'channel':
            # Добавление бота в администраторы канала
            pass

    elif old.is_chat_admin() and new.is_chat_admin():
        # Изменение каких-либо прав администратора
        pass

    elif not old.is_chat_member() and new.is_chat_admin():
        # Повышение бота до администратора
        pass

    elif not old.is_chat_member() and new.is_chat_member():
        # Добавление бота в чат без прав администратора
        pass

    elif old.is_chat_admin() and not new.is_chat_admin():
        # Понижение бота в чате с администратора до обычного пользователя
        pass

    elif old.is_chat_member() and not new.is_chat_member():
        # Удаление бота из чата/канала
        pass
