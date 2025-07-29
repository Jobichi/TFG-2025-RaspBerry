FROM python:3.11-slim

WORKDIR /app

COPY telegram-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram-bot/bot.py .

# NO copiamos el .env para no meter claves en la imagen
CMD ["python", "bot.py"]

#docker build -t telegram-bot .
#docker run -d --name telegram-bot --env-file telegram-bot/config.env telegram-bot
