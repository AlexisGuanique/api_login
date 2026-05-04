# API: guardado de cuentas (`user_agent` + `cookie`)

Resumen para integrar otra app con este servicio: qué enviar al guardar cuentas y cómo se comporta el endpoint.

---

## Endpoint

| Método | Ruta | Auth |
|--------|------|------|
| `POST` | `/api/accounts/save/<user_id>` | Token (mismo esquema `token_required` del proyecto) |

---

## Cuerpo JSON

Se acepta una de estas formas en la raíz del JSON:

- **`accounts`**: array de objetos cuenta, o  
- **`account`**: un solo objeto (equivalente a una sola cuenta).

---

## Campos obligatorios por cuenta

| Campo | Descripción |
|--------|-------------|
| **`user_agent`** | Cadena (`string`) **no vacía** tras quitar espacios al inicio y al final. Es el User-Agent **de esa cuenta/sesión**. Ya no se toma de configuración por navegador en el servidor. |
| **`email`** | Obligatorio, con valor. |
| **`password`** | Obligatorio, con valor. |
| **`cookie`** | Obligatorio. Puede ser **string** (p. ej. JSON de cookies), **array** u **object**; el servidor lo normaliza y persiste (típicamente como JSON en texto). |

### Ejemplo mínimo

```json
{
  "accounts": [
    {
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
      "email": "cuenta@ejemplo.com",
      "password": "secreto",
      "cookie": "[{\"name\":\"session\",\"value\":\"abc123\"}]"
    }
  ]
}
```

---

## Validación relevante

- Si falta `user_agent`, no es `string`, o es solo espacios → **400** con cuerpo que puede incluir `invalid_accounts` (índice, objeto enviado y lista `missing_fields`).
- Emails **duplicados dentro de la misma petición** → **400**.
- Cuenta cuyo `email` **ya existe** para ese `user_id` → no se inserta de nuevo; la respuesta indica duplicados y contadores (`saved_count`, `duplicate_emails`, etc.).

---

## Consumo posterior (bots / otras apps)

Al obtener cuentas (por ejemplo `POST /api/accounts/next/<user_id>` u otros listados), cada objeto incluye **`user_agent`** y **`cookie`**. El cliente debe usar el **`user_agent` devuelto con esa cuenta**, no un mapa de UA por navegador desde el servidor (esa configuración fue retirada).

---

## Nota de contexto

El User-Agent **viaja con cada cuenta** al guardar y al leer la cola. La UI de “User-Agent por navegador” y la tabla asociada en servidor ya no aplican para este flujo.

Para más detalle del cambio de modelo y migraciones, ver `docs/cuentas-user-agent-por-cuenta.md`.
