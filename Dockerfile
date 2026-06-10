FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# rembg 모델 사전 다운로드 (첫 요청 지연 방지)
RUN python -c "from rembg import remove; remove(b'')" 2>/dev/null || true

COPY . .

EXPOSE 7860

ENV PYTHONUNBUFFERED=1
CMD ["python", "-u", "app.py"]
