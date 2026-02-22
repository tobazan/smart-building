FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY sensors.py main.py ./

ENV PYTHONUNBUFFERED=1

EXPOSE 47808/udp 5020

CMD ["python", "main.py"]
