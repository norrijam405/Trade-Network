FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

COPY requirements-preview.txt ./
RUN pip install --no-cache-dir -r requirements-preview.txt

COPY hosted_preview.py preview_runner.py ./

EXPOSE 8000

CMD ["sh", "-c", "uvicorn preview_runner:app --host 0.0.0.0 --port ${PORT:-8000}"]
