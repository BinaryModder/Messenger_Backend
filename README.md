# Messenger_Backend

Backend for android-messenger. FastAPI + PostgreSQL + WebSocket.

## Requirements

- Python 3.11+
- Docker Desktop

## Запуск

```sh
docker compose up -d --build
```

API Docs: http://localhost:8000/docs
- WebSocket Test Client: http://localhost:8080

## API

### Users
- `POST /api/v1/users/register` - Регистрация
- `POST /api/v1/users/login` - Вход
- `GET /api/v1/users/{id}` - Профиль пользователя

### Chats
- `POST /api/v1/chats` - Создать чат
- `GET /api/v1/chats?user_id={id}` - Список чатов пользователя (только те, где он участник)
- `GET /api/v1/chats/{id}` - Информация о чате
- `PATCH /api/v1/chats/{id}` - Обновить чат
- `DELETE /api/v1/chats/{id}` - Удалить чат

### Chat Members
- `GET /api/v1/chats/{id}/members` - Участники чата
- `POST /api/v1/chats/{id}/members/{user_id}` - Добавить участника
- `DELETE /api/v1/chats/{id}/members/{user_id}` - Удалить участника

### Messages
- `GET /api/v1/chats/{id}/messages` - Сообщения чата
- `POST /api/v1/chats/{id}/messages` - Отправить сообщение
- `PATCH /api/v1/chats/{id}/messages/{message_id}` - Редактировать сообщение
- `DELETE /api/v1/chats/{id}/messages/{message_id}` - Удалить сообщение

## WebSocket

Подключение: `ws://localhost:8000/ws?user_id={id}`

### Actions (отправка)
- `send_message` - Отправить сообщение
- `edit_message` - Редактировать сообщение
- `delete_message` - Удалить сообщение
- `get_history` - Получить историю чата
- `ping` - Проверка соединения

### Events (получение)
- `new_message` - Новое сообщение
- `message_updated` - Сообщение обновлено
- `message_deleted` - Сообщение удалено
- `user_status` - Статус пользователя (online/offline)
- `chat_history` - История чата

### Пример
```json
{
  "action": "send_message",
  "chat_id": 1,
  "text": "Hello!"
}
```

## Архитектура

- **REST API** - HTTP endpoints для CRUD операций
- **WebSocket** - Реальное время для сообщений и уведомлений
- **PostgreSQL** - Хранение данных
- **Nginx** - Статический фронтенд для тестирования
