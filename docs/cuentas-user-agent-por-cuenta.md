# Cuentas: User-Agent por cuenta (cambio de contrato API)

Documentación de las modificaciones relacionadas con el **User-Agent** al guardar cuentas y con la eliminación de la configuración por navegador en servidor.

**Fecha de referencia:** mayo 2026.

---

## Contexto

Antes, el User-Agent podía gestionarse en la interfaz web por navegador (`bot_browser_user_agent`) y el servidor lo enviaba a los bots en comandos WebSocket.

Ahora el **User-Agent forma parte de cada cuenta**: se envía y persiste con la cuenta en la API de accounts. La tabla y la UI de “User-Agent por navegador” fueron retiradas; los clientes deben enviar `user_agent` en cada objeto de cuenta al guardar.

---

## Endpoint afectado (principal)

| Método | Ruta | Autenticación |
|--------|------|----------------|
| `POST` | `/api/accounts/save/<user_id>` | Header de token (mismo mecanismo que `@token_required` del proyecto) |

**Cuerpo JSON (raíz):**

- `accounts`: lista de objetos **o**
- `account`: un solo objeto (equivalente a una lista de un elemento)

Cada objeto de cuenta debe incluir:

| Campo | Tipo | Obligatorio | Notas |
|-------|------|-------------|--------|
| `user_agent` | `string` | Sí | Debe ser una cadena **no vacía** tras quitar espacios al inicio y final. No se acepta solo espacios ni tipos que no sean string. |
| `email` | `string` | Sí | Debe estar presente y ser “truthy” (comportamiento existente). |
| `password` | `string` | Sí | Igual que `email`. |
| `cookie` | `string` \| `array` \| `object` | Sí | Se normaliza a string JSON almacenado en BD (comportamiento existente). |

**Persistencia:** el valor guardado en base de datos para `user_agent` es `(user_agent or "").strip()`.

**Respuestas habituales:**

- `400` — Sin `accounts`/`account`, formato inválido, campos faltantes (incluido `user_agent` inválido), emails duplicados en la misma petición, o error al procesar `cookie`.
- `201` — Al menos una cuenta nueva insertada.
- `200` — Petición válida pero ninguna cuenta nueva (por ejemplo, todas ya existían para ese `user_id`).
- `500` — Error interno al guardar.

En error de validación por cuenta, la respuesta puede incluir `invalid_accounts` con `index`, `account` y `missing_fields` (lista de claves que fallaron, p. ej. `user_agent`).

---

## Comportamiento nuevo frente al anterior

1. **`user_agent` obligatorio y tipado**  
   Si falta la clave, no es `str`, o es `str` vacío / solo espacios, la cuenta se considera inválida y se devuelve `400` con detalle en `invalid_accounts`.

2. **Ya no hay User-Agent “global por navegador” en servidor**  
   Los clientes que solo subían cookie/email/password deben **añadir `user_agent` por cuenta** en el mismo payload de `/save`.

3. **Migración de base de datos**  
   Revisión Alembic `eliminar_bot_browser_user_agent`: elimina la tabla `bot_browser_user_agent`. Tras desplegar, ejecutar migraciones (`flask db upgrade` o el flujo del proyecto).

---

## Otros endpoints de accounts (sin cambio de ruta, mismo dato)

El campo `user_agent` sigue devolviéndose en las respuestas donde ya se serializaba la cuenta, por ejemplo:

- `GET /api/accounts/` (admin)
- `POST /api/accounts/user/<user_id>`
- `POST /api/accounts/next/<user_id>` (cuenta consumida de la cola)

El bot o cualquier cliente debe usar el **`user_agent` del objeto cuenta** devuelto por la API, no un mapa por navegador desde el servidor.

---

## Comandos a bots (WebSocket)

En `POST /api/bots/command/<bot_id>`, el payload emitido al bot incluye:

- `remote_user_agent`: `null`
- `remote_user_agents`: `{}`

La intención es que el **UA de sesión salga del registro de cuenta** (guardado vía `/api/accounts/save/...` y leído vía `/next` u otros listados), no de configuración por navegador en el panel web.

---

## Resumen para integradores

1. Al llamar `POST /api/accounts/save/<user_id>`, incluir **`user_agent`** en cada cuenta, cadena no vacía (tras trim).
2. Aplicar migraciones para eliminar `bot_browser_user_agent`.
3. Actualizar bots/clientes que dependían de `remote_user_agents` / `remote_user_agent` en el socket para leer `user_agent` desde cada cuenta.
