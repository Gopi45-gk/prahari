FROM python:3.10-slim

WORKDIR /app

RUN pip install redis

COPY services/simulators/main.py .

CMD ["python", "main.py"]
