# 1. Use Python 3.11 (Stable with Pandas 2.0.3)
FROM python:3.11-slim

# 2. Set working directory
WORKDIR /app

# 3. Install system dependencies (optional but good for reliability)
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements and install
# We use --upgrade to ensure we get compatible latest versions of dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 5. Copy the application code
COPY . /app

# 6. Network configuration
EXPOSE 8080

# 7. Start Command
# This looks for the 'app' object inside 'api/app.py'
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "api.app:app", "--timeout", "120"]