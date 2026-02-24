# Use a lightweight Python image
FROM python:3.9-slim

WORKDIR /app

# Install dependencies (This will now take 2 seconds instead of 5 minutes!)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Run the app with multiple workers for high concurrency
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app", "--timeout", "30", "--workers", "2"]
