FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dealz ./dealz
COPY tests ./tests
RUN mkdir -p /app/var
EXPOSE 8000
CMD ["python", "-m", "dealz.main"]
