FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir mysql-connector-python==9.0.0

COPY db_test.py .

CMD ["python", "db_test.py"]
