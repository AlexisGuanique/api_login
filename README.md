# API de Autenticación con Flask

Esta aplicación proporciona una API RESTful construida con Flask para la gestión de usuarios, autenticación y verificación de tokens.

---

## Requisitos previos

1. Python 3.9 o superior.
2. Docker y Docker Compose instalados en tu sistema.
3. Archivo `.env` con las siguientes variables configuradas:

```env
ADMIN_KEY=my_very_secret_key_example
DATABASE_PATH=/api_login/app/database/users.db
DATABASE_PATH_DEV=database/users.db
```

---

## Configuración del entorno virtual

1. **Crear el entorno virtual:**

   ```bash
   python -m venv venv
   ```

2. **Activar el entorno virtual:**

   - En macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - En Windows:
     ```bash
     .\venv\Scripts\activate
     ```

3. **Instalar las dependencias:**

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## Ejecutar la aplicación localmente

1. **Configurar las variables de entorno:**

   Asegúrate de tener un archivo `.env` en el directorio principal con las configuraciones necesarias.

2. **Ejecutar la aplicación:**

   ```bash
   flask run --host=0.0.0.0 --port=8080
   ```

La aplicación estará disponible en: [http://localhost:8080](http://localhost:8080)

---

## Ejecutar la aplicación con Docker

1. **Construir la imagen de Docker:**

   ```bash
   docker build -t api_login .
   ```

2. **Ejecutar el contenedor:**

   ```bash
   docker run -d -p 8080:8080 --env-file .env --name api_login_container api_login
   ```

La aplicación estará disponible en: [http://localhost:8080](http://localhost:8080)

---

## Endpoints de la API

### **1. Obtener todos los usuarios**
**GET** `/api/auth/users`

#### Headers:
- `Admin-Key`: (Requerido) La clave de administrador para autenticar.

#### Respuesta:
```json
{
  "message": "Usuarios obtenidos exitosamente",
  "users": [
    {
      "id": 1,
      "username": "admin",
      "password": "<hashed_password>",
      "token_expiration": "2025-02-28 12:00:00",
      "access_token": "<token>"
    }
  ]
}
```

---

### **2. Obtener un usuario por ID**
**GET** `/api/auth/user/<id>`

#### Headers:
- `Admin-Key`: (Requerido) La clave de administrador para autenticar.

#### Respuesta:
```json
{
  "message": "Usuario obtenido exitosamente",
  "user": {
    "id": 1,
    "username": "admin",
    "password": "<hashed_password>",
    "token_expiration": "2025-02-28 12:00:00",
    "access_token": "<token>"
  }
}
```

---

### **3. Modificar un usuario**
**PUT** `/api/auth/user/<id>`

#### Headers:
- `Admin-Key`: (Requerido) La clave de administrador para autenticar.

#### Body:
```json
{
  "username": "nuevo_username",
  "password": "nueva_password"
}
```

#### Respuesta:
```json
{
  "message": "Usuario actualizado exitosamente",
  "user": {
    "id": 1,
    "username": "nuevo_username",
    "password": "<hashed_password>",
    "token_expiration": "2025-02-28 12:00:00",
    "access_token": "<token>"
  }
}
```

---

### **4. Registrar un usuario**
**POST** `/api/auth/register`

#### Headers:
- `Admin-Key`: (Requerido) La clave de administrador para autenticar.

#### Body:
```json
{
  "username": "nuevo_usuario",
  "password": "password_seguro"
}
```

#### Respuesta:
```json
{
  "message": "Usuario registrado exitosamente",
  "user": {
    "id": 2,
    "username": "nuevo_usuario",
    "access_token": "<token>",
    "token_expiration": "2025-02-28 12:00:00"
  }
}
```

---

### **5. Eliminar un usuario**
**DELETE** `/api/auth/user/<id>`

#### Headers:
- `Admin-Key`: (Requerido) La clave de administrador para autenticar.

#### Respuesta:
```json
{
  "message": "Usuario eliminado exitosamente",
  "user_id": 2
}
```

---

### **6. Login**
**POST** `/api/auth/login`

#### Body:
```json
{
  "username": "admin",
  "password": "password123"
}
```

#### Respuesta:
```json
{
  "message": "Login exitoso",
  "access_token": "<token>",
  "expires_in": "2025-02-28 12:00:00"
}
```

---

### **7. Logout**
**POST** `/api/auth/logout`

#### Respuesta:
```json
{
  "message": "Logout exitoso"
}
```

---

### **8. Verificar token**
**POST** `/api/auth/verify-token`

#### Body:
```json
{
  "access_token": "<token>"
}
```

#### Respuesta:
- **Token válido:**
```json
{
  "message": "Token válido",
  "is_valid": true,
  "username": "admin"
}
```
- **Token inválido o expirado:**
```json
{
  "message": "El token ha expirado",
  "is_valid": false
}
```

---

## Consideraciones finales

1. Asegúrate de proteger la `SECRET_KEY` y el `ADMIN_KEY`.
2. Usa Gunicorn o un servidor WSGI para producción.
3. Verifica los permisos de escritura en el directorio de la base de datos para evitar errores al crearla.

Para cualquier problema o mejora, no dudes en contactarme.

