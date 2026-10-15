FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py questions.json ./
RUN mkdir -p /data
ENV DATABASE=/data/exam.sqlite3 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "app:app"]
