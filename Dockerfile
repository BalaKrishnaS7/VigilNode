FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Non-root user for security
RUN useradd -m vigiluser && chown -R vigiluser:vigiluser /app
USER vigiluser

EXPOSE 5000

CMD ["python", "run.py"]
