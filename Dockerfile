FROM python:3.9-slim

# 1. Install system dependencies required for Playwright
# These are the Linux libraries that Chrome/Firefox need to run
RUN apt-get update && apt-get install -y \
    wget \
    libipc-run-perl \
    libgstreamer-gl1.0-0 \
    libgstreamer-plugins-bad1.0-0 \
    gstreamer1.0-plugins-good \
    libenchant-2-2 \
    libsecret-1-0 \
    libmanette-0.2-0 \
    libgles2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Install Playwright Browsers (Chromium only to save space)
RUN playwright install chromium
RUN playwright install-deps chromium

# 4. Copy Application Code
COPY . .

# 5. Run the app
# Increased timeout to 60s
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app", "--timeout", "60"]
