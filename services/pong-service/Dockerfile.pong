FROM python:3.11-slim

WORKDIR /app

# Instalamos cliente MQTT
RUN pip install paho-mqtt

COPY pong.py /app/

# Ejecución en modo "unbuffered" (-u) para que los print salgan al log
CMD ["python", "-u", "pong.py"]
