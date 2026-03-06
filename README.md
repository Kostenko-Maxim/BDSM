# BDSM-бот (Broadcast Distribution & Scheduling Manager)

Telegram-бот для управления рассылками и отложенным постингом в каналах.

## Возможности

- **Админ-панель** через inline-кнопки бота (суперадмин / админ)
- **Рассылка** текста, фото, видео, документов, анимаций, голосовых в каналы
- **Пересылка** — перешлите боту любое сообщение, он опубликует его от имени канала
- **Отложенные посты** — укажите дату/время и бот опубликует автоматически
- **Управление каналами** — добавление, отключение, удаление

## Стек

- Python 3.11+
- aiogram 3.x
- SQLAlchemy 2.0 (async) + asyncpg
- PostgreSQL
- APScheduler
- Poetry

## Установка

### 1. Клонировать проект

```bash
git clone <repo-url>
cd bdsm-bot
```

### 2. Установить зависимости

```bash
poetry install
```

### 3. Настроить окружение

```bash
cp .env.example .env
```

Отредактируйте `.env`:

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `SUPERADMIN_ID` | Ваш Telegram ID (числовой) |
| `DATABASE_URL` | URL подключения к PostgreSQL |
| `TIMEZONE` | Часовой пояс (по умолчанию `Europe/Moscow`) |

### 4. Создать базу данных

```bash
createdb bdsm_bot
```

### 5. Применить миграции (или auto-create)

Таблицы создаются автоматически при первом запуске. Для управления миграциями:

```bash
poetry run alembic revision --autogenerate -m "initial"
poetry run alembic upgrade head
```

### 6. Запуск

```bash
poetry run python -m bot
```

## Использование

1. Напишите боту `/start`
2. Добавьте бота администратором в нужные каналы
3. В меню «Каналы» подключите их (перешлите сообщение из канала или отправьте `@username`)
4. Создавайте рассылки через «Новая рассылка»
5. Планируйте отложенные посты через кнопку «Отложить»

## Структура проекта

```
bot/
├── __main__.py          # Точка входа
├── config.py            # Настройки
├── loader.py            # Экземпляр бота
├── db/
│   ├── engine.py        # Async engine
│   ├── models.py        # ORM-модели
│   └── repositories.py  # CRUD
├── handlers/
│   ├── start.py         # /start, главное меню
│   ├── admin.py         # Управление админами
│   ├── channels.py      # Управление каналами
│   ├── broadcast.py     # Рассылка
│   └── schedule.py      # Отложенные посты
├── keyboards/
│   └── inline.py        # Inline-клавиатуры
├── middlewares/
│   └── auth.py          # Проверка прав
├── services/
│   ├── broadcaster.py   # Отправка в каналы
│   └── scheduler.py     # Планировщик
└── states/
    └── broadcast.py     # FSM-состояния
```
