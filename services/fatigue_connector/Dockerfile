FROM python:3.10-slim

WORKDIR /app

RUN pip install redis websockets

COPY services/fatigue_connector/main.py .

CMD ["python", "main.py"]
