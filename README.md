# AntiCrash Bot

Русскоязычный Discord anti-crash / anti-nuke бот на `Python + Disnake` с интерактивной slash-панелью `/anticrash_manage`, локальным SQLite-хранилищем и готовым `start.sh` для Ubuntu.

## О проекте

Этот проект предназначен для защиты Discord-сервера от опасных действий staff-ролей: массового удаления каналов, выдачи опасных прав, банов, киков, массовых упоминаний, добавления ботов, работы с вебхуками и других типовых anti-nuke сценариев.

Бот хранит отдельные лимиты для каждой staff-роли, поддерживает whitelist, trusted roles, лог-канал и несколько вариантов наказания. Интерфейс полностью на русском языке и управляется через `select menu`, `buttons` и `modals`.

## Разработка

Проект написан разработчиком при поддержке **OpenAI Codex**.

Codex использовался как инженерный помощник:

- для ускорения проектной структуры
- для генерации черновой реализации отдельных модулей
- для выравнивания интерфейсов и логики
- для проверки части сценариев и тестового покрытия

Архитектурные решения, финальная логика, доработка поведения и контроль результата остаются за разработчиком.

## Возможности

- Slash-команда `/anticrash_manage`
- Полностью русскоязычный embed-интерфейс
- Отдельные настройки для каждой staff-роли
- Значение защиты: `Запрещено` или числовой лимит
- Единое окно лимитов: `60 секунд`
- `Whitelist` пользователей и `trusted roles`
- Наказания: `remove_roles`, `kick`, `ban`
- Логирование нарушений в указанный канал
- Работа через audit logs там, где Discord не даёт исполнителя напрямую
- Совместимость с локальной SQLite-базой `data/anticrash.sqlite`

## Реализованные защиты

- `bot_add`
- `channel_create`
- `channel_delete`
- `channel_update`
- `role_create`
- `role_delete`
- `role_update`
- `role_grant`
- `role_remove`
- `member_ban`
- `member_unban`
- `member_kick`
- `member_timeout`
- `dangerous_permissions`
- `mass_mentions`
- `webhook_create`
- `webhook_delete`

## Как это работает

1. Администратор или владелец сервера открывает `/anticrash_manage`.
2. Выбирает staff-роль, для которой будут действовать ограничения.
3. Для каждой защиты задаёт режим:
   - `Запрещено`
   - числовой лимит за 60 секунд
4. При нарушении бот определяет исполнителя через audit logs или напрямую из события.
5. Если у участника несколько staff-ролей, применяется самая строгая политика:
   - `Запрещено` имеет приоритет над лимитом
   - если лимитов несколько, берётся минимальный
6. Исключения работают для:
   - владельца сервера
   - самого бота
   - пользователей из whitelist
   - участников с trusted roles
7. После нарушения бот применяет наказание и отправляет лог в лог-канал.

## Стек

- Python 3.11+
- Disnake
- sqlite3
- python-dotenv

## Структура проекта

```text
bot/
  main.py
  config.py
  anticrash/
    constants.py
    repository.py
    service.py
    views.py
    listeners.py
    session_store.py
data/
tests/
requirements.txt
start.sh
README.md
```

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните значения:

```env
DISCORD_TOKEN=your-bot-token
DISCORD_CLIENT_ID=your-application-client-id
DISCORD_GUILD_ID=your-test-guild-id
```

## Быстрый старт

### Windows

```powershell
Copy-Item .env.example .env
py -m pip install -r requirements.txt
py -m bot.main
```

### Linux / macOS

```bash
cp .env.example .env
python3 -m pip install -r requirements.txt
python3 -m bot.main
```

## Запуск на Ubuntu

В проекте уже есть `start.sh`, который:

- проверяет наличие `python3`
- создаёт `.venv`, если окружение ещё не создано
- активирует виртуальное окружение
- обновляет `pip`
- ставит зависимости из `requirements.txt`
- проверяет наличие `.env`
- создаёт папку `data/`
- запускает бота через `python -m bot.main`

Использование:

```bash
cp .env.example .env
nano .env
chmod +x start.sh
./start.sh
```

## Настройка бота

1. Убедитесь, что бот приглашён с правами на:
   - audit log
   - управление ролями и каналами
   - баны, кики, таймауты
   - webhooks
2. В Discord Developer Portal включите privileged intent `Server Members`.
3. Запустите бота.
4. Используйте `/anticrash_manage`.

### Что можно настроить в панели

- staff-роль
- лимиты и запреты на действия
- наказание для роли
- лог-канал
- whitelist
- trusted roles

## Проверка работы

### Ручной сценарий

1. Создайте тестовую staff-роль.
2. Выдайте её тестовому аккаунту, который ниже бота по иерархии.
3. В панели выставьте:
   - `Удаление каналов` -> `Запрещено`
   - `Создание ролей` -> `2`
4. Укажите наказание и лог-канал.
5. Попробуйте удалить канал тестовым аккаунтом.
6. Попробуйте создать 3 роли меньше чем за минуту.
7. Проверьте, что бот:
   - применил наказание
   - отправил embed-лог
8. Добавьте пользователя в whitelist и убедитесь, что защита на него больше не срабатывает.

### Автотесты

```bash
python -m unittest
```

Покрыто:

- strictest policy
- sliding window 60 секунд
- bypass через whitelist и trusted roles
- mass mention detection
- repository smoke test

## Где что менять

- `bot/anticrash/constants.py` — список защит, labels и action keys
- `bot/anticrash/listeners.py` — привязка Discord-событий к action keys
- `bot/anticrash/service.py` — лимиты, bypass, наказания и логирование
- `bot/anticrash/views.py` — embed-интерфейс и interaction flow
- `bot/anticrash/repository.py` — работа с SQLite

## Ограничения текущей версии

- `mass_mentions` сейчас реагирует на `@everyone`, `@here` или 5+ суммарных упоминаний пользователей и ролей
- для `kick`, `ban` и `remove_roles` бот должен стоять выше нарушителя по иерархии
- audit log события могут приходить с небольшой задержкой, поэтому обработка опирается только на свежие записи

## Для GitHub

Этот README оформлен как стартовая GitHub-страница проекта: он кратко объясняет назначение бота, стек, запуск, структуру и роль Codex в процессе разработки.
