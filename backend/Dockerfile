FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DATA_DIR=/data PORT=8701
EXPOSE 8701
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8701"]
