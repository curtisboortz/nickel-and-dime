FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DEMO_MODE=1
ENV PORT=8080

EXPOSE 8080

CMD gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
