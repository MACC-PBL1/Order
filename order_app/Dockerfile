FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /home/pyuser/code

# Copy requirements and install globally
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -u 1000 -m pyuser && \
    chown -R pyuser:pyuser /home/pyuser

# Copy entrypoint and app
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
COPY app ./app

# Switch to non-root user
USER pyuser

# Entrypoint
ENTRYPOINT ["./entrypoint.sh"]
