# Подключение Bitrix24 к GPM Platform

## 1. Получение Webhook URL

1. Перейдите в **Bitrix24** → **Администратор** → **Интеграция** → **Боты**
2. Нажмите **Создать бота**
3. Заполните параметры:
   - **Название**: GPM Platform Bot
   - **Доступные методы**: Выберите все CRM методы (leads, contacts, deals)
4. Скопируйте **Webhook URL** (выглядит так):
   ```
   https://ваш_домен.bitrix24.ru/rest/1/abc123def456ghi789/
   ```

## 2. Добавьте в файл `.env`

```env
BITRIX24_WEBHOOK=https://ваш_домен.bitrix24.ru/rest/1/abc123def456ghi789/
```

## 3. Установите зависимости

```bash
flutter pub get
```

## 4. Использование сервиса

### Создание заказа (Lead)
```dart
final result = await bitrix24.createOrder(
  title: 'Разгрузка мебели',
  address: 'ул. Ленина, 10',
  workersCount: 3,
  hours: 4,
  description: 'Разгрузить 2 машины мебели',
  clientEmail: 'client@example.com',
  clientPhone: '+7 (900) 123-45-67',
);

if (result['success']) {
  print('Заказ создан! ID: ${result['orderId']}');
}
```

### Получение всех заказов
```dart
List<Map<String, dynamic>> orders = await bitrix24.getOrders();
for (var order in orders) {
  print('${order['title']} - ${order['status']}');
}
```

### Регистрация грузчика/логиста
```dart
final result = await bitrix24.createContact(
  name: 'Иван Сидоров',
  email: 'ivan@example.com',
  phone: '+7 (900) 123-45-67',
  role: 'worker', // или 'logist'
);

if (result['success']) {
  print('Контакт создан! ID: ${result['contactId']}');
}
```

### Получение контактов
```dart
List<Map<String, dynamic>> contacts = await bitrix24.getContacts();
```

### Обновление статуса заказа
```dart
bool success = await bitrix24.updateOrderStatus(
  'LEAD_ID_123',
  'IN_PROGRESS', // NEW, IN_PROGRESS, WON, LOSE
);
```

### Добавление комментария
```dart
bool success = await bitrix24.addComment(
  'LEAD_ID_123',
  'Заказ принят, ожидаем подтверждения от грузчиков',
);
```

### Создание сделки (для отслеживания доходов)
```dart
final result = await bitrix24.createDeal(
  title: 'Выполнение заказа',
  amount: 5000,
  contactId: 'CONTACT_ID_123',
);
```

### Получение финансовой статистики
```dart
Map<String, dynamic> stats = await bitrix24.getFinancialStats();
print('Доход: ${stats['totalIncome']} ₽');
print('Сделок: ${stats['totalDeals']}');
print('Средняя сделка: ${stats['averageDeal']} ₽');
```

## 5. Статусы заказов в Bitrix24

- `NEW` - Новый заказ
- `IN_PROGRESS` - В процессе
- `WON` - Завершён
- `LOSE` - Отменён

## 6. Особенности Bitrix24

### Плюсы:
- ✅ Полностью российский сервис
- ✅ Встроенная CRM
- ✅ Видимость истории операций
- ✅ Интеграции с бухгалтерией
- ✅ Чаты и уведомления

### Минусы:
- ❌ Небольшая задержка при большом объёме запросов
- ❌ Ограничение на количество API вызовов в день (для бесплатного плана)

## 7. Тестирование

Используйте Postman для тестирования API:

```bash
POST https://ваш_домен.bitrix24.ru/rest/1/abc123def456ghi789/crm.lead.add
Content-Type: application/x-www-form-urlencoded

fields={"TITLE":"Test Order","PHONE":[{"VALUE":"+7-900-000-00-00"}]}
```

## 8. Справка по полям Lead (Заказ)

| Поле | Описание | Пример |
|------|---------|--------|
| TITLE | Название заказа | Разгрузка мебели |
| PHONE | Телефон клиента | +7 (900) 123-45-67 |
| EMAIL | Email клиента | client@example.com |
| STATUS_ID | Статус | NEW, IN_PROGRESS, WON |
| COMMENTS | Комментарии | Описание работ |
| SOURCE_ID | Источник | CONTACT_FORM |

## 9. Дополнительные ресурсы

- [Документация Bitrix24 API](https://dev.1c-bitrix.ru/rest_help/)
- [Bitrix24 REST API CRM](https://dev.1c-bitrix.ru/rest_help/crm/leads/)
- [Установка Bitrix24](https://www.bitrix24.ru/)

---

**Готово!** Ваше приложение теперь использует Bitrix24 вместо Supabase.
