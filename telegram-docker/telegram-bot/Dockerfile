FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

COPY config.env /app/config.env
ENV $(cat /app/config.env | xargs)

CMD ["python", "bot.py"]
