FROM python:3.10-slim

WORKDIR /app

COPY services/convergence_engine/requirements.txt .
RUN pip install -r requirements.txt

COPY services/convergence_engine/main.py .

EXPOSE 8001

CMD ["python", "main.py"]
