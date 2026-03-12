from __future__ import annotations

from dataclasses import dataclass


DEFAULT_WINDOW_SECONDS = 60
DEFAULT_PUNISHMENT = "remove_roles"
MASS_MENTION_THRESHOLD = 5


@dataclass(frozen=True)
class ActionDefinition:
    key: str
    label: str
    event_label: str
    description: str


@dataclass(frozen=True)
class ServiceOption:
    key: str
    label: str
    description: str


ACTION_DEFINITIONS = (
    ActionDefinition("bot_add", "Добавление ботов", "Добавление бота", "Кто и сколько раз добавляет ботов на сервер."),
    ActionDefinition("channel_create", "Создание каналов", "Создание канала", "Создание новых каналов."),
    ActionDefinition("channel_delete", "Удаление каналов", "Удаление канала", "Удаление существующих каналов."),
    ActionDefinition("channel_update", "Редактирование каналов", "Редактирование канала", "Изменение имени, прав и других параметров канала."),
    ActionDefinition("role_create", "Создание ролей", "Создание роли", "Создание новых ролей."),
    ActionDefinition("role_delete", "Удаление ролей", "Удаление роли", "Удаление ролей."),
    ActionDefinition("role_update", "Редактирование ролей", "Редактирование роли", "Изменение прав и свойств роли."),
    ActionDefinition("role_grant", "Выдача ролей", "Выдача роли", "Выдача ролей участникам."),
    ActionDefinition("role_remove", "Снятие ролей", "Снятие роли", "Снятие ролей с участников."),
    ActionDefinition("member_ban", "Бан участников", "Бан участника", "Блокировка участников сервера."),
    ActionDefinition("member_unban", "Разбан участников", "Разбан участника", "Снятие бана с участников."),
    ActionDefinition("member_kick", "Кик участников", "Кик участника", "Выгон участников с сервера."),
    ActionDefinition("member_timeout", "Выдача таймаута", "Выдача таймаута", "Выдача timeout участникам."),
    ActionDefinition("dangerous_permissions", "Выдача админ-прав на роль", "Выдача админ-прав", "Назначение роли с правами администратора."),
    ActionDefinition("mass_mentions", "Запрещённые пинги", "Массовые упоминания", "Сообщения с @everyone / @here или большим числом упоминаний."),
    ActionDefinition("webhook_create", "Создание вебхуков", "Создание вебхука", "Создание новых webhook-ов."),
    ActionDefinition("webhook_delete", "Удаление вебхуков", "Удаление вебхука", "Удаление webhook-ов."),
)

ACTIONS_BY_KEY = {definition.key: definition for definition in ACTION_DEFINITIONS}

PUNISHMENT_OPTIONS = (
    {"value": "remove_roles", "label": "Снять роли", "description": "Снять все управляемые staff-роли нарушителя."},
    {"value": "kick", "label": "Кикнуть", "description": "Выгнать нарушителя с сервера."},
    {"value": "ban", "label": "Забанить", "description": "Забанить нарушителя."},
)

SERVICE_OPTIONS = (
    ServiceOption("setting:punishment", "Наказание для staff-группы", "Выберите, что делать при нарушении лимита."),
    ServiceOption("setting:log_channel", "Лог-канал", "Укажите канал для логов anticrash."),
    ServiceOption("setting:trusted_roles", "Trusted роли", "Добавить или удалить роли-исключения."),
)

ACTION_SELECT_OPTIONS = tuple(
    [{"value": f"action:{action.key}", "label": action.label, "description": action.description[:100]} for action in ACTION_DEFINITIONS]
    + [{"value": option.key, "label": option.label, "description": option.description} for option in SERVICE_OPTIONS]
)
