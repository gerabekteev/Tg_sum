FROM python:3.11-slim

# Установка рабочей директории внутри контейнера
WORKDIR /app

# Отключение буферизации логов Python для мгновенного отображения в Docker Compose
ENV PYTHONUNBUFFERED=1

# Копирование требований и их установка
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование остального исходного кода
COPY . .

# Запуск приложения
CMD ["python", "main.py"]
