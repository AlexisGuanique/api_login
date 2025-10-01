FROM python:3.9.10-alpine3.14

WORKDIR /api_login

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . /api_login

ENV PYTHONPATH=/api_login
ENV FLASK_APP=app:app
ENV FLASK_ENV=production
ENV DATABASE_PATH=/api_login/app/database
ENV ADMIN_KEY=my_very_secret_key

EXPOSE 80

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:80", "app:app"]
