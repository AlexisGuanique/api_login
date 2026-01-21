"""
Punto de entrada para Flask que soporta WebSockets.
Permite usar 'flask --app app --debug run' con soporte WebSocket completo.

NOTA: Para que WebSockets funcionen correctamente con 'flask run',
debes ejecutar: python -m app en lugar de 'flask run',
o usar: python app.py

Si usas 'flask run', el servidor de desarrollo de Werkzeug no soporta
WebSockets correctamente y las conexiones se perderán cuando el servidor
se reinicie.
"""

from app import app, socketio

# Sobrescribir el método run para usar SocketIO cuando se ejecute directamente
def run_with_socketio(host='127.0.0.1', port=5000, debug=False, **options):
    """Ejecuta la aplicación usando SocketIO para soportar WebSockets."""
    print("🚀 Iniciando servidor Flask con WebSockets...")
    print(f"📡 WebSocket habilitado en http://{host}:{port}")
    if debug:
        print("🐛 Modo debug activado")
    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        use_reloader=debug,  # Solo usar reloader si está en modo debug
        allow_unsafe_werkzeug=True  # Necesario para desarrollo con threading
    )

# Reemplazar el método run
app.run = run_with_socketio

# Si se ejecuta directamente (python app.py), usar SocketIO
if __name__ == "__main__":
    import sys
    # Obtener host y port de los argumentos si están presentes
    host = '127.0.0.1'
    port = 5000
    debug = '--debug' in sys.argv or '-d' in sys.argv
    
    if '--host' in sys.argv:
        idx = sys.argv.index('--host')
        if idx + 1 < len(sys.argv):
            host = sys.argv[idx + 1]
    if '--port' in sys.argv:
        idx = sys.argv.index('--port')
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])
    
    run_with_socketio(host=host, port=port, debug=debug)

# Exportar app para que Flask lo detecte
__all__ = ['app']

