FROM python:3.11-slim

WORKDIR /app

# Instalamos cliente MQTT
RUN pip install paho-mqtt

COPY pong.py /app/

CMD ["python", "pong.py"]
