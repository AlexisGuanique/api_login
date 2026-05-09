# Bot Creador: recepción de User-Agents

Esta guía documenta cómo recibe los User-Agents el bot al iniciar el proceso creator.

## 1) Origen de los User-Agents

1. **Mapa por nombre de navegador** (configuración web en `web/bot-config`):
   - Un campo de texto por cada perfil del catálogo sincronizado (mismo nombre que usa el bot, p. ej. `BraveNormal`, `Chrome`).
   - Se persiste en `bot_global_config.creator_user_agents_by_browser_json` como objeto JSON `{ "NombreNavegador": "Mozilla/5.0 ...", ... }`.
   - Los valores de ese mapa (sin duplicar claves) también alimentan el **pool** que puede rellenar o forzar `user_agent` al guardar cuentas vía `POST /api/accounts/save/…` (ver `docs/README_API_GUARDADO_CUENTAS.md`).

2. **Lista legacy** (`creator_user_agents_json`):
   - Solo se usa como **respaldo** si el mapa por navegador está vacío y aún existiera una lista antigua en BD.

3. **User-Agent por cuenta**:
   - Cada cuenta en `/api/accounts/save/<user_id>` puede llevar su `user_agent`.
   - Al consumir `/api/accounts/next/<user_id>`, cada fila devuelta incluye su `user_agent`.

## 2) Payload WebSocket que recibe el bot

Cuando se envía comando al bot (`/api/bots/command/<bot_id>`), llega un evento `command` con este bloque relevante para creator:

```json
{
  "command": "execute_creator",
  "bot_id": 123,
  "preferred_browser": "BraveNormal",
  "preferred_browsers": ["BraveNormal", "Chrome"],
  "remote_creator_user_agents_by_browser": {
    "BraveNormal": "Mozilla/5.0 ...",
    "Chrome": "Mozilla/5.0 ..."
  },
  "remote_creator_user_agent": "Mozilla/5.0 ...",
  "remote_creator_user_agents": [
    "Mozilla/5.0 ...",
    "Mozilla/5.0 ..."
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

- **`remote_creator_user_agents_by_browser`**: mapa **nombre de navegador → User-Agent**. El bot debe elegir la clave que coincida con el perfil que está ejecutando.
- **`remote_creator_user_agent`**: UA recomendado para la sesión actual: el del `preferred_browser` si existe en el mapa; si no, primer elemento de la lista legacy (si aplica).
- **`remote_creator_user_agents`**: lista de todos los UA del mapa (o la lista legacy), útil para compatibilidad con clientes que solo leían la lista.

Si no hay UAs configurados, `remote_creator_user_agents_by_browser` es `{}`, `remote_creator_user_agent` puede ser `null` y `remote_creator_user_agents` es `[]`.

## 3) Recomendación de consumo en el bot

1. Si `remote_creator_user_agents_by_browser` tiene la clave del navegador en ejecución, usar **ese** string.
2. Si no, usar `remote_creator_user_agent` si viene definido.
3. Para cuentas ya en cola, preferir el `user_agent` de cada account desde `/api/accounts/next/<user_id>`.

## 4) Formato en la pantalla de configuración

- Un input por perfil del catálogo; el **nombre del perfil** es la clave en el JSON.
- Los navegadores marcados como **globales** deben tener UA no vacío antes de guardar.

## 5) Vaciar

En `web/bot-config`, **«Vaciar User-Agents por navegador»** limpia `creator_user_agents_by_browser_json` y `creator_user_agents_json`.
