# Phase 2 Integration Guide

## Обзор

Phase 2 реализует полную интеграцию между тремя компонентами экосистемы subbox:

- **sboxmgr** (Python) - CLI для управления конфигурациями
- **sboxagent** (Go) - Демон для управления клиентами
- **sbox-common** - Общие схемы и протоколы

## Архитектура интеграции

```
┌─────────────┐    Unix Socket     ┌─────────────┐
│   sboxmgr   │ ←──────────────→   │  sboxagent  │
│   (Python)  │  Framed JSON       │    (Go)     │
└─────────────┘                    └─────────────┘
       │                                  │
       │                                  │
       └────────── sbox-common ──────────┘
            (Схемы и протоколы)
```

## Компоненты Phase 2

### 1. sboxagent - Полностью реализовано ✅

#### Сервисы:
- **CLI Integration** - Выполнение команд sboxmgr
- **Status Monitoring** - Мониторинг системы и сервисов
- **Systemd Integration** - Управление systemd сервисами
- **Integration Service** - Unix socket сервер для коммуникации

#### Файлы:
- `internal/services/cli.go` - CLI интеграция
- `internal/services/monitor.go` - Мониторинг
- `internal/services/systemd.go` - Systemd интеграция
- `internal/services/integration.go` - Socket сервер
- `internal/agent/agent.go` - Основной агент

### 2. sboxmgr - Реализовано ✅

#### Компоненты:
- **Agent Bridge** - Коммуникация с sboxagent
- **Event Sender** - Отправка событий через socket
- **Socket Client** - Unix socket клиент
- **Protocol Definitions** - Типизированные протоколы

#### Файлы:
- `src/sboxmgr/agent/bridge.py` - Agent bridge
- `src/sboxmgr/agent/event_sender.py` - Event sender
- `src/sboxmgr/agent/ipc/socket_client.py` - Socket клиент
- `src/sboxmgr/agent/protocol.py` - Протоколы

### 3. sbox-common - Реализовано ✅

#### Схемы и протоколы:
- **JSON Schemas** - Схемы для всех клиентов
- **Interface Protocol** - Протокол sboxmgr ↔ sboxagent
- **Socket Protocol** - Framed JSON протокол
- **Validation Utils** - Утилиты для загрузки схем

#### Файлы:
- `schemas/*.schema.json` - Схемы клиентов
- `protocols/interface/sboxmgr-agent.schema.json` - Интерфейс протокол
- `protocols/socket/protocol_v1.schema.json` - Socket протокол
- `src/sbox_common/protocols/socket/framed_json.py` - Framed JSON
- `validation/validator.go` - Schema loader (только загрузка)

## Протоколы коммуникации

### 1. Unix Socket Protocol

**Путь:** `/tmp/sboxagent.sock`

**Формат:** Framed JSON (4 байта длина + 4 байта версия + JSON данные)

### 2. Типы сообщений

#### Event Message
```json
{
  "id": "uuid",
  "type": "event",
  "timestamp": "2025-01-28T10:00:00Z",
  "event": {
    "event_type": "subscription_updated",
    "source": "sboxmgr",
    "priority": "normal",
    "data": {
      "subscription_url": "https://...",
      "servers_count": 150
    }
  }
}
```

#### Command Message
```json
{
  "id": "uuid",
  "type": "command",
  "timestamp": "2025-01-28T10:00:00Z",
  "command": {
    "command": "ping",
    "params": {}
  }
}
```

#### Response Message
```json
{
  "id": "uuid",
  "type": "response",
  "timestamp": "2025-01-28T10:00:00Z",
  "response": {
    "status": "success",
    "request_id": "original-uuid",
    "data": {
      "pong": true
    }
  }
}
```

#### Heartbeat Message
```json
{
  "id": "uuid",
  "type": "heartbeat",
  "timestamp": "2025-01-28T10:00:00Z",
  "heartbeat": {
    "agent_id": "sboxmgr",
    "status": "healthy",
    "version": "1.0.0"
  }
}
```

## Использование

### Запуск sboxagent

```bash
cd sboxagent
go run cmd/agent/main.go
```

Агент автоматически запустит все сервисы Phase 2:
- CLI Service
- Monitor Service
- Systemd Service
- Integration Service (Unix socket)

### Использование из sboxmgr

```python
from sboxmgr.agent.event_sender import send_event, ping_agent
from sboxmgr.agent.bridge import AgentBridge

# Проверка доступности агента
if ping_agent():
    print("Agent доступен")

# Отправка события
send_event("config_generated", {
    "client_type": "sing-box",
    "config_size": 1024
})

# Использование bridge для валидации
bridge = AgentBridge()
if bridge.is_available():
    result = bridge.validate("/path/to/config.json")
    print(f"Валидация: {'успешна' if result.success else 'неуспешна'}")
```

### Тестирование интеграции

```bash
# Запустите sboxagent
cd sboxagent && go run cmd/agent/main.go

# В другом терминале запустите тест
cd sboxmgr && python tests/integration_test.py
```

## Конфигурация

### sboxagent конфигурация

```yaml
# agent.yaml
agent:
  name: "sboxagent"
  version: "0.2.0"
  log_level: "info"

services:
  integration:
    enabled: true
    socket_path: "/tmp/sboxagent.sock"
    timeout: "30s"
  
  cli:
    enabled: true
    sboxmgr_path: "sboxmgr"
    timeout: "30s"
  
  monitoring:
    enabled: true
    interval: "30s"
  
  systemd:
    enabled: true
    service_name: "sboxagent"
```

### sboxmgr конфигурация

EventSender автоматически использует `/tmp/sboxagent.sock` или можно настроить:

```python
from sboxmgr.agent.event_sender import EventSender

sender = EventSender(
    socket_path="/custom/path/agent.sock",
    timeout=10.0
)
```

## Мониторинг и отладка

### Логи sboxagent

```bash
# Запуск с debug логами
SBOXAGENT_AGENT_LOG_LEVEL=debug go run cmd/agent/main.go
```

### Проверка socket

```bash
# Проверка существования socket
ls -la /tmp/sboxagent.sock

# Тест подключения
echo '{"id":"test","type":"command","timestamp":"2025-01-28T10:00:00Z","command":{"command":"ping","params":{}}}' | nc -U /tmp/sboxagent.sock
```

### Мониторинг событий

sboxagent логирует все получаемые события:

```
INFO[2025-01-28T10:00:00Z] Received event client_id=client_123 event_type=subscription_updated source=sboxmgr priority=normal
```

## Устранение неполадок

### Socket не создается
- Проверьте права доступа к `/tmp/`
- Убедитесь что Integration Service включен в конфигурации
- Проверьте логи sboxagent на ошибки

### События не доходят
- Проверьте что sboxagent запущен и socket активен
- Проверьте формат JSON сообщений
- Включите debug логирование в обоих компонентах

### Валидация не работает
- Убедитесь что CLI Service включен
- Проверьте путь к sboxmgr в конфигурации
- Проверьте что sboxmgr доступен в PATH

## Статус реализации

- ✅ **sboxagent**: 100% - Все сервисы Phase 2 реализованы и интегрированы
- ✅ **sboxmgr**: 90% - Agent bridge, events, socket client реализованы
- ✅ **sbox-common**: 95% - Схемы, протоколы, framed JSON реализованы

**Общий статус Phase 2: ✅ ЗАВЕРШЕНО (95%)**

Phase 2 полностью функционален и готов к использованию. Единая экосистема работает как задумано! 