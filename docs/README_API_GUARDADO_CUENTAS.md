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

Opcional en la raíz:

- **`force_creator_pool_user_agents`**: si es `true`, **ignora** el `user_agent` enviado por cuenta y asigna uno de la lista guardada en **`/web/bot-config`** (lista creator), en **rotación** por índice (`i % n`). Requiere que esa lista no esté vacía.

Si **no** usas esa bandera y en servidor **sí** hay lista creator: cualquier cuenta cuyo `user_agent` venga vacío o solo espacios se rellena automáticamente desde esa misma lista (rotación por posición en el lote).

---

## Campos obligatorios por cuenta

| Campo | Descripción |
|--------|-------------|
| **`user_agent`** | Cadena (`string`) **no vacía** tras quitar espacios (salvo que el servidor la complete desde la lista creator como arriba). Si envías un valor explícito, es el que se guarda salvo que actives `force_creator_pool_user_agents`. |
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

- Si falta `user_agent` usable (vacío y sin lista creator en servidor, o no es `string` tras rellenar) → **400** con `invalid_accounts` cuando corresponda.
- `force_creator_pool_user_agents` sin lista en bot-config → **400** con mensaje claro.
- Emails **duplicados dentro de la misma petición** → **400**.
- Cuenta cuyo `email` **ya existe** para ese `user_id` → no se inserta de nuevo; la respuesta indica duplicados y contadores (`saved_count`, `duplicate_emails`, etc.).

---

## Consumo posterior (bots / otras apps)

Al obtener cuentas (por ejemplo `POST /api/accounts/next/<user_id>` u otros listados), cada objeto incluye **`user_agent`** y **`cookie`**. El cliente debe usar el **`user_agent` devuelto con esa cuenta**, no un mapa de UA por navegador desde el servidor (esa configuración fue retirada).

---

## Nota de contexto

El User-Agent **viaja con cada cuenta** al guardar y al leer la cola. La lista masiva de creator en **`/web/bot-config`** es la misma fuente que puede rellenar o forzar el `user_agent` al guardar, para que coincida con lo “registrado” en servidor si así lo configuras.

Para más detalle del cambio de modelo y migraciones, ver `docs/cuentas-user-agent-por-cuenta.md`.
