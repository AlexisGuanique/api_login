FROM python:3.9.10-alpine3.14

WORKDIR /api_login

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . /api_login

WORKDIR /api_login/app

ENV PYTHONPATH=/api_login
ENV FLASK_APP=__init__

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]

