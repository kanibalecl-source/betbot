FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-c", "print('PYTHON_OK'); import time; time.sleep(999999)"]
RUN echo "DOCKERFILE_OK"
