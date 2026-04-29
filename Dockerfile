FROM python:3.11-slim

# System deps for ifcopenshell
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Persistent volume for SQLite DB
VOLUME ["/app/backend/data"]

EXPOSE 8000

CMD ["python", "backend/main.py"]
