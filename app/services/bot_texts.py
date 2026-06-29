# ========================= Messages =========================
RULES_MSG = '''Пожалуйста, ознакомьтесь с правилами бота:
1. Любой заказ необходимо выполнить в полном объеме.
2. Исполнитель не позднее, чем за 2ч до заказа, обязан подтвердить логисту свой выход на заказ.
3. На адрес заказа исполнитель обязан прибыть не позднее, чем за 5 минут до начала работы.
4. Недопустимо нахождение заказа в состоянии какого-либо опьянения.
5. Исполнитель обязан соблюдать трудовую дисциплину, необходимые меры безопасности при проведении работ, следовать инструкциям Заказчика и не создавать конфликтных ситуаций.
6. Исполнитель обязан после завершения работ заполнить «Лист учета рабочего времени/Табель» и направить Диспетчеру его фото, а также номер карты на оплату.
7. Исполнитель обязан иметь с собой для работы: верхнюю одежду с закрытым рукавом, штаны и ботинки.
В случае нарушения указанных правил оплата исполнителя может быть задержана для дополнительных разбирательств
Также в случае нарушений следующих пунктов предусмотрены штрафы:
Опоздание - 10-60 мин - 100-600руб
Невыход на заказ - 2000руб
Прибытие на заказ или нахождение на заказе в любом виде опьянения - без оплаты 
Выход на заказы в шортах/тапочках - 500руб
Случаи компенсации при отмене заказа:
1. Отмена более, чем за 1.5ч до начала заказа -  без компенсации.
2. Отмена менее, чем за 1.5ч до начала заказа -  компенсация фактически понесенных расходов на проезд, подтвержденных документально.
3. Отмена по факту прибытия - половина минималки по минимальной ставке группы. 
4. Отмена по факту прибытия с ожиданием решения по отмене от 2х часов - полная минималка по минимальной ставке группы.
Правила округлений:
1. При завершении заказа между полным часов и 15 минутами нового - округление в сторону полного предыдущего часа (например: при завершении в 17:12 округляться будет до 17:00)
2. При завершении заказа между 16 минутами и 44 - до 30 минут (например: завершенный в 17:44 заказ округляется до 17:30)
3. При завершении заказа после 45 минут - до полного следующего часа (например: завершенный в 17:51 заказ округляется до 18:00)
Пользовательское соглашение:
Политика в отношении персональных данных – https://clck.ru/3Ctm5R .

Нажимая 'Согласен',  вы подтверждаете, что с условиями ознакомлены и согласны.
'''

SHARE_CONTACT_MSG = '''
<b>Регистрация 📗</b>
 
Давай пройдем быструю регистрацию, чтобы ты мог получать заказы на работу!
Для начала поделись своим номером телефона по кнопке ниже 👇
'''
SHARE_LOCATION_MSG = '''
<b>Включи геолокацию/местоположение на телефоне</b>
Отправь свой город, чтобы получать заказы без ошибок 👇
'''
SELECT_LOCATION_MSG = '''
Выбери город(-а), в которых ты собираешься работать <b>и нажми "Подтвердить" внизу списка</b> 📍'''

FIND_LOCATION_MSG = '''
Найден город: <b>{city}</b>

Выбери город(-а), в которых ты собираешься работать
'''

SELECTED_LOCATION_MSG = '''
<b>Выбранные города</b> 📍

'''

BEFORE_SEND_NAME_MSG = 'Мы почти закончили, осталось совсем немного и ты сможешь получать Заказы!'
SEND_SURNAME_MSG = 'Введи только свою <b>ФАМИЛИЮ</b>!'
SEND_FIRST_NAME_MSG = 'Введи только свое <b>ИМЯ</b>!'
SEND_MIDDLE_NAME_MSG = 'Введи только свое <b>ОТЧЕСТВО</b>!'

SEND_DATE_BIRTH_MSG = '''
Введи дату рождения в формате <b>ДД.ММ.ГГГГ</b>

Например: <b>01.01.1994</b>
'''
SEND_PASSPORT_PHOTO_MSG = '''
Прикрепи фото паспорта
'''
SEND_NATIONALITY_MSG = '''
Ты гражданин Российской Федерации?
'''
SEND_STRAPS_MSG = '''
Есть ли у вас такелажные ремни? 
'''
SEND_TOOLS_MSG = '''
Есть ли у вас шуруповерт или другие инструменты
'''

CONFIRM_CHANGE_NATIONALITY_MSG = '''
Вы уверены, что хотите изменить гражданство?
'''

SUCCESS_REGISTER_MSG = '''
Готово!
Переходи на канал <b>«{bot_title}»</b> (там будут заказы)

Как перейдешь - обязательно нажми кнопку «Запустить/Начать/Старт/Start» (без этого заказы не будут появляться!) 👇
'''
SUCCESS_CHANGE_CITY_MSG = '''
Готово!
Твой город изменен
Переходи на канал <b>«{bot_title}»</b> (там будут заказы)

Как перейдешь - обязательно нажми кнопку «Запустить/Начать/Старт/Start» (без этого заказы не будут появляться!) 👇
'''
REGISTER_ALREADY_MSG = '''
Ты уже зарегистрирован!
'''

LOCATION_NOT_REQUIRED_MSG = '''
Специалисты в данном регионе не требуются
'''

LOCATION_NOT_SELECTED_MSG = 'Вы не выбрали ни одного региона'

WRONG_DATE_BIRTH_MSG = 'Неверный формат даты рождения. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ'
WRONG_LOCATION_MSG = 'Мы не нашли город по вашему местоположению'

# REQUEST
REQUEST_PHONE_MSG = 'Телефон: {phone}'
REQUEST_NAME_MSG = 'ФИО: {name}'
REQUEST_DATE_BIRTH_MSG = 'Дата рождения: {date_birth}'
REQUEST_NATIONALITY_MSG = 'Гражданство РФ: {nationality}'
REQUEST_LOCATION_MSG = 'Город(-а): {location}'
REQUEST_DELETED_CITY = 'Удаленный город'
CHANGE_DATA_SUCCESS_MSG = 'Данные успешно изменены'


OPERATOR_REQUEST_SEND_MSG = '''
Ваша заявка принята, ожидайте подтверждения от администратора
'''

NEW_OPERATOR_REQUEST_MSG = '''
<b>Новая заявка (оператор)</b> 📗

Telegram ID: {telegram_id}
Пользователь: @{username}
'''

ADMIN_CONFIRM_REQUEST_MSG = '<b>Заявка подтверждена</b> ✅'
ADMIN_DECLINE_REQUEST_MSG = '<b>Заявка отклонена</b> ❌'

OPERATOR_REQUEST_CONFIRM_MSG = 'Ваша заявка подтверждена. Введите команду /start для начала работы'
OPERATOR_REQUEST_DECLINE_MSG = 'Ваша заявка отклонена'

OPERATOR_MENU_MSG = 'Меню оператора'

# Operator menu
OPERATOR_SELECT_CITY_MSG = 'Выберите город'
OPERATOR_SELECT_REGION_MSG = 'Выберите регион'
OPERATOR_SEND_ORDER_ID_MSG = 'Отправьте номер заказа'
OPERATOR_SEND_DATE_MSG = '''
Отправьте дату и время выполнения работ в формате ДД.ММ.ГГГГ ЧЧ:ММ

Например: 01.01.2021 12:00
'''
OPERATOR_SEND_PEOPLE_MSG = 'Сколько людей требуется?'
OPERATOR_SEND_METRO_MSG = 'Укажите ближайшую станцию метро'
OPERATOR_SEND_ADDRESS_MSG = '''
Укажите адрес

Например, Шмитовский проезд 16с1
❗️ Не используйте сокращения д., ул.
'''
OPERATOR_CHOICE_NATIONALITY_MSG = 'Выберите гражданство'
OPERATOR_CHOICE_ADDRESS_MSG = 'Выбран адрес: <b>{address}</b>'
OPERATOR_SEND_COMMENT_MSG = 'Напишите характер работ'
OPERATOR_SEND_PRICE_HOUR_MSG = 'Укажите стоимость за час (наемник)'
OPERATOR_SEND_PRICE_REGULAR_MSG = 'Укажите стоимость за час (штатный постоянного графика)'
OPERATOR_SEND_PRICE_STATE_MSG = 'Укажите стоимость за час (штатный свободного графика)'
OPERATOR_SEND_MIN_TIME_MSG = 'Укажите минимальное время оплаты'

REQUEST_CITY_MSG = 'Город: <u>{city}</u>'
REQUEST_ORDER_ID_MSG = 'Номер заказа: {order_id}'
REQUEST_DATE_MSG = 'Дата и время выполнения работ: <u>{date}</u>'
REQUEST_PEOPLE_MSG = 'Кол-во людей: <u>{people}</u>'
REQUEST_NATIONAL_MSG = 'Гражданство РФ: <u>{national}</u>'
REQUEST_METRO_MSG = 'Метро: <u>{metro}</u>'
REQUEST_ADDRESS_MSG = 'Адрес: 👉 <a href="https://yandex.ru/maps/?ll={lon},{lat}&z=12&text={lat},{lon}">{address}</a>'
REQUEST_MANUAL_ADDRESS_MSG = 'Адрес: 👉 {address}'
REQUEST_COMMENT_MSG = 'Характер работы: {comment}'
REQUEST_PRICE_REGULAR_MSG = 'Ставка (штатный постоянного графика) : <u>{price_regular}</u>'
REQUEST_PRICE_STATE_MSG = 'Ставка (штатный свободного графика) : <u>{price_state}</u>'
REQUEST_PRICE_HOUR_MSG = 'Ставка (наемник): <u>{price_hour}</u>'
REQUEST_MIN_TIME_MSG = 'Минимальная оплата: <u>{min_time}</u>'
REQUEST_STATUS_MSG = 'Статус: {status}'

OPERATOR_WRONG_DATE_FORMAT_MSG = 'Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ ЧЧ:ММ'
OPERATOR_WRONG_PEOPLE_AMOUNT_FORMAT_MSG = 'Количество людей должно быть числом и не более 150'

SENDING_MSG = '🔄 Отправка...'
SENDING_MSG_2 = '🔄 Заявка рассылается'

SENDING_SUCCESS_MSG = '✅ Отправлено пользователям: {count}'
OPEN_REQUEST_START_MESSAGING = 'Заявка {order_id} открыта'
OPEN_REQUESTS_MSG = 'Заявка {order_id} отправлена {count}'
CLOSE_REQUESTS_MSG = 'Заявка {order_id} закрыта, отправлено {count}'
OPEN_AGAIN_REQUESTS_MSG = 'Заявка {order_id} снова открыта, отправлено {count}'

MY_REQUESTS_MSG = 'Заявки'

ALREADY_OPERATOR_MSG = 'Вы уже зарегистрированы в качестве оператора'

YOUNGER_MSG = 'Для прохождения регистрации вам должно быть больше 18 лет'

SEARCH_BY_NUMBER_MSG = 'Введите номер заявки'

FIND_ADDRESS_MSG = 'Найден адрес: {address}'
FIND_MORE_ADDRESS_MSG = '''
Найдены адреса:
{address_list}

<i>Выберите необходимый из списка</i>
'''

OPERATOR_WRONG_ADDRESS_MSG = 'Неверный адрес. Пожалуйста, введите адрес в формате: Шмитовский проезд 16с1'
NOT_IMPLEMENTER_MSG = 'Вы не являетесь исполнителем'
WAIT_CONFIRM_DATA_MSG = 'Дождитесь подтверждения данных оператором'
NO_ORDERS_MSG = 'У вас нет активных заказов'
ORDERS_MSG = 'Ваши активные заказы'

IMPLEMENTER_STAT_MSG = '''
<b>Ваша статистика</b>

Статус: <code>{status}</code>
Взял заказов: <code>{take_orders}</code>
Успешно выполнено: <code>{success_orders}</code>
Провалено: <code>{fail_orders}</code>
'''

CONFIRM_ODER_DECLINE_MSG = 'Вы уверены, что хотите отказаться от заказа?'
ORDER_DECLINED_MSG = 'Вы отказались от заказа'
ORDER_DECLINED_BY_IMPLEMENTER_MSG = 'Исполнитель @{username} отказался от заказа {order_id}'
FILTER_REQUESTS_MSG = 'Фильтр заявок'
ENTER_USER_USERNAME_MSG = 'Введите username пользователя'

COMPLETE_WITHOUT_IMP = 'Завершить заказы без исполнителей'
CONFIRM_COMPLETE = 'Вы уверены что хотите завершить все закрытые заказы без исполнителей?'
COMPLETION_MSG = '🔄 Заявки завершаются'
# ========================= Buttons =========================

BACK_BTN = '« Назад'
MAIN_MENU_BTN = 'Главное меню'
SKIP_BTN = 'Пропустить'
CONFIRM_BTN = 'Подтвердить'
DECLINE_BTN = 'Отклонить'
YES_BTN = 'Да'
NO_BTN = 'Нет'

SHARE_CONTACT_BTN = '👉 👉 👉 Поделиться номером телефона 👈 👈 👈'
SHARE_LOCATION_BTN = '👉 👉 👉 Отправить Город 👈 👈 👈'

TAKE_REQUEST_BTN = 'Взять заказ'

CHECKED_BTN = '✅ '

CHANGE_DATA_BTN = 'Изменить данные'
CHANGE_NAME_BTN = 'Изменить имя'
CHANGE_SURNAME_BTN = 'Изменить фамилию'
CHANGE_MIDDLE_NAME_BTN = 'Изменить отчество'
CHANGE_DATE_BIRTH_BTN = 'Изменить дату рождения'
CHANGE_PASSPORT_PHOTO_BTN = 'Заменить фото паспорта'
CHANGE_NATIONALITY_BTN = 'Изменить гражданство'
CHANGE_PHONE_BTN = 'Изменить телефон'

MY_REQUESTS_BTN = 'Мои заказы'
ACTIVE_REQUESTS_BTN = 'Активные заказы'
CLOSE_REQUESTS_BTN = 'Закрытые заказы'
COMPLETED_REQUESTS_BTN = 'Завершенные заказы'
SEARCH_BY_NUMBER_BTN = 'Поиск по номеру'
ADD_REQUEST_BTN = 'Добавить заказ'
IMPLEMENTERS_BTN = 'Исполнители'
FILTER_BTN = 'Фильтр'

CHANGE_CITY_BTN = 'Изменить город'
CHANGE_ORDER_ID_BTN = 'Изменить номер заказа'
CHANGE_DATE_BTN = 'Изменить дату'
CHANGE_PEOPLE_BTN = 'Изменить кол-во людей'
CHANGE_NATIONAL_BTN = 'Изменить гражданство'
CHANGE_METRO_BTN = 'Изменить метро'
CHANGE_ADDRESS_BTN = 'Изменить адрес'
CHANGE_COMMENT_BTN = 'Изменить характер работ'
CHANGE_PRICE_REGULAR_BTN = 'Изменить ставку постоянный график'
CHANGE_PRICE_STATE_BTN = 'Изменить ставку свободный график'
CHANGE_PRICE_HOUR_BTN = 'Изменить ставку наемник'
CHANGE_MIN_TIME_BTN = 'Изменить мин. время оплаты'

RUSSIAN_BTN = 'РФ'
NOT_RUSSIAN_BTN = 'Нет'
EVERY_ONE_BTN = 'Любой'

ENTER_AGAIN_BTN = 'Ввести другой'
GET_LOCATION_BTN = 'Показать на карте'

SELECT_BTN = 'Выбрать'
PREV_BTN = '⬅️'
NEXT_BTN = '➡️'
CLOSE_BTN = 'Закрыть'
OPEN_BTN = 'Открыть'

# Admin
OPERATORS_BTN = 'Операторы'
BOTS_BTN = 'Боты'
DELETE_OPERATOR_BTN = 'Удалить оператора'
DELETE_BOT_BTN = 'Удалить бота'
ADD_BOT_BTN = 'Добавить бота'
ADD_REGION_BTN = 'Добавить регион'
BLOCK_BTN = 'Заблокировать'

# Команды

USERS_CMD = '/users - Команда отображения общего числа пользователей и пользователей прошедших проверки (Админ)'
DATA_CMD = '/data @username  - Команда отображающая данные исполнителя по username '
BLOCK_CMD = '/block @username  - Команда блокировки пользователя'
UNBLOCK_CMD = '/unblock @username   - Команда разблокировки пользователя '
ENABLE_CMD = '/enable_geocoder - Команда ручного включения АПИ яндекс карт (Админ)'
DISABLE_CMD = '/disable_geocoder - Команда ручного выключения АПИ яндекс карт (Админ) '
RESET_CMD = '/reset_state @username - Команда сброса состояния бота с пользователем (Админ)' 
STATS_CMD = '/stats @username - Команда статистики оператора по приоритетным группам'
GET_PRIORITY_CMD = '/get_priority @username - Команда отображающая приоритетную группу исполнителя'
MAIL_CMD = '/mail - Команда массовой рассылки (Админ)'
SEAL_CMD= '/seal @username - снимает иммунитет оператора к блокировке по кол-ву незавершенных заказов (Админ)'
UNSEAL_CMD= '/unseal @username - устанавливает иммунитет оператора к блокировке по кол-ву незавершенных заказов (Админ)'
EMPLOY_CMD = '/employ @username - устанавливает статус штатный исполнителю'
UNEMPLOY_CMD = '/unemploy @username - устанавливает статус подрядчик исполнителю'
PLANERKA_CMD = '/planerka - Команда массовой рассылки для штатных (Админ)'
CMD_LIST = [USERS_CMD,DATA_CMD,BLOCK_CMD,UNBLOCK_CMD,RESET_CMD,ENABLE_CMD,DISABLE_CMD,STATS_CMD,GET_PRIORITY_CMD,MAIL_CMD,EMPLOY_CMD,UNEMPLOY_CMD,PLANERKA_CMD]
