# Bot Creador: recepción de User-Agents

Esta guía documenta cómo recibe los User-Agents el bot al iniciar el proceso creator.

## 1) Origen de los User-Agents

Hay dos fuentes complementarias:

1. **Lista global de creator** (configuración web):
   - Se edita en `web/bot-config` en el cuadro de texto (un User-Agent por línea).
   - Lo mostrado es lo guardado en servidor; al guardar se persiste en `bot_global_config.creator_user_agents_json`.

2. **User-Agent por cuenta**:
   - Cada cuenta en `/api/accounts/save/<user_id>` lleva su `user_agent`.
   - Al consumir `/api/accounts/next/<user_id>`, cada account devuelta incluye su `user_agent`.

## 2) Payload WebSocket que recibe el bot

Cuando se envía comando al bot (`/api/bots/command/<bot_id>`), llega un evento `command` con este bloque relevante:

```json
{
  "command": "execute_creator",
  "bot_id": 123,
  "preferred_browser": "Chrome",
  "preferred_browsers": ["Chrome", "Firefox"],
  "remote_creator_user_agents": [
    "Mozilla/5.0 ...",
    "Mozilla/5.0 ...",
    "..."
  ],
  "remote_creator_time_config": {
    "scheduled_time": null,
    "timezone": null,
    "cycle_time_minutes": 0,
    "time_config_type": "cycle",
    "accounts_per_cycle": 1
  },
  "remote_domain_config": {
    "global_config": {},
    "domains": [],
    "random_tlds": []
  }
}
```

### Significado de campos UA

- `remote_creator_user_agents`: **lista completa** de UAs para creator (campo único global para UAs de creator).

Si no hay lista cargada en la web, este campo llega como lista vacía (`[]`).

## 3) Recomendación de consumo en el bot

Prioridad sugerida para el bot creator:

1. Usar `remote_creator_user_agents` si viene con elementos.
2. Además, para ejecución por cuenta, usar el `user_agent` incluido en cada account obtenida por `/api/accounts/next/<user_id>`.

## 4) Formato en la pantalla de configuración

- Una línea = un User-Agent.
- Líneas vacías se ignoran.
- Duplicados se eliminan automáticamente (comparación case-insensitive).

Ejemplo:

```text
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.7672.61 Safari/537.36
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.1755.42 Safari/537.36
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5137.56 Safari/537.36
```

## 5) Vaciar lista

En `web/bot-config` existe botón **“Vaciar lista de User-Agents”**:
- Limpia `creator_user_agents_json` en BD.
- En siguientes comandos creator, la lista global se enviará vacía.
