FROM python:3.9.10-alpine3.14

WORKDIR /api_login

# Instalar dependencias del sistema
RUN apk add --no-cache gcc musl-dev

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . /api_login

ENV PYTHONPATH=/api_login
ENV FLASK_APP=app:app
ENV FLASK_ENV=production
ENV SOCKETIO_ASYNC_MODE=eventlet

EXPOSE 80

# Usar gunicorn con eventlet worker para soportar WebSockets con Flask-SocketIO
# -w 1: 1 worker (Flask-SocketIO requiere 1 worker para WebSockets)
# --timeout 120: timeout para requests largos
# --worker-class eventlet: necesario para WebSockets con Flask-SocketIO
# --worker-connections 1000: máximo de conexiones por worker
# --bind 0.0.0.0:80: escuchar en todas las interfaces en puerto 80
# --access-logfile -: mostrar logs de acceso en stdout
# --error-logfile -: mostrar logs de error en stdout
# --log-level info: nivel de logging
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:80", "--timeout", "120", "--worker-class", "eventlet", "--worker-connections", "1000", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "app:app"]
