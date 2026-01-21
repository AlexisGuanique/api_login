#!/usr/bin/env python
"""
Script de inicio para el servidor en producción.
Usa gunicorn con eventlet worker para soportar WebSockets.
"""
import os
import sys

# Asegurar que el path esté configurado
sys.path.insert(0, '/api_login')

# Importar la aplicación
from app import app, socketio

if __name__ == '__main__':
    # Obtener host y port de variables de entorno
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '80'))
    
    print(f"🚀 Iniciando servidor Flask con WebSockets...")
    print(f"📡 Escuchando en http://{host}:{port}")
    print(f"🔧 Async mode: {socketio.async_mode}")
    
    # Ejecutar con SocketIO
    socketio.run(
        app,
        host=host,
        port=port,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=False
    )

