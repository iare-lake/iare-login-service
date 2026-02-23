FROM python:3.9

# Install system dependencies for Chrome + Playwright
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium)
RUN playwright install --with-deps chromium

COPY . .

# Run with Gunicorn - single worker to avoid threading issues
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:10000", "app:app", "--timeout", "120"]