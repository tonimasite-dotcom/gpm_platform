# Подготовленное подключение адресов через Яндекс Карты

Статус: выключено. Текущий provider — DaData. Яндекс включается только после
отдельного решения владельца и закрытия перечисленных ниже лицензионных вопросов.

Подготовленная форма использует два серверных API:

1. API Геосаджеста — варианты адресов во время ввода.
2. API Геокодера — запрос после выбора дома для получения координат.

Будущие production-ключи должны храниться только в server environment:

```text
YANDEX_GEOSUGGEST_API_KEY=<секрет>
YANDEX_GEOCODER_API_KEY=<секрет>
```

Не добавлять реальные значения в Git, Flutter `.env`, tracked YAML, CI-логи или
документацию. Подготовленный код находится только в локальной ветке
`feature/address-provider-switch` (`6ac65d0`, `f06e540`) и не опубликован в
`main`/production.

## Лицензионное условие до production

GPM сохраняет выбранный адрес и координаты в заказе. До включения Яндекса для
реальных заказов владелец должен подтвердить тариф и лицензию, разрешающие такое
хранение. Нужно отдельно подтвердить допустимость схемы без встроенной карты.

Документация:

- https://yandex.ru/maps-api/docs/suggest-api/quickstart.html
- https://yandex.ru/maps-api/docs/geocoder-api/quickstart.html
- https://yandex.ru/dev/tariffs/doc/ru/geosuggest/prices/
- https://yandex.ru/dev/tariffs/doc/ru/geocoder/prices/
- https://yandex.ru/dev/tariffs/doc/ru/geocoder/terms/
