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

EXPOSE 80

# Gunicorn con eventlet para soportar WebSockets
# -w 4: 4 workers (ajusta según CPU de tu instancia)
# --timeout 120: timeout para requests largos
# --worker-class eventlet: necesario para WebSockets con Flask-SocketIO
# --max-requests 1000: reinicia workers después de 1000 requests (previene memory leaks)
# --max-requests-jitter 50: variación aleatoria para evitar reinicios simultáneos
# Para WebSockets con Flask-SocketIO, usar eventlet directamente
# Alternativa: gunicorn con eventlet worker (comentado abajo)
CMD ["python", "-m", "eventlet.wsgi", "--bind", "0.0.0.0:80", "--listen", "1000", "app:app"]
# Alternativa con gunicorn (descomentar si prefieres):
# CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:80", "--timeout", "120", "--worker-class", "eventlet", "--worker-connections", "1000", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
