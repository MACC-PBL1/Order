FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /home/pyuser/code

COPY Chassis/dist/microservice_chassis-0.3.0-py3-none-any.whl ./Chassis/dist/

# Copy requirements and install globally
COPY Order/order_app/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -u 1000 -m pyuser && \
    chown -R pyuser:pyuser /home/pyuser

# Copy entrypoint and app
COPY Order/order_app/entrypoint.sh .
RUN chmod +x entrypoint.sh
COPY Order/order_app/app ./app

# Crea la carpeta donde se guardará la public key
RUN mkdir -p /tmp/keys && chmod -R 777 /tmp/keys


# Switch to non-root user
USER pyuser

# Entrypoint
ENTRYPOINT ["./entrypoint.sh"]
