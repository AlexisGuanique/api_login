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

# Gunicorn con configuración para múltiples usuarios simultáneos
# -w 4: 4 workers (ajusta según CPU de tu instancia)
# --timeout 120: timeout para requests largos
# --workers-class sync: clase de workers (sync es bueno para I/O bound)
# --max-requests 1000: reinicia workers después de 1000 requests (previene memory leaks)
# --max-requests-jitter 50: variación aleatoria para evitar reinicios simultáneos
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:80", "--timeout", "120", "--worker-class", "sync", "--max-requests", "1000", "--max-requests-jitter", "50", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
