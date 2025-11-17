FROM apache/airflow:2.8.0-python3.10

USER root

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Copiar requirements
COPY requirements.txt /tmp/requirements.txt

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copiar archivos de configuración (opcional)
# COPY airflow.cfg /opt/airflow/airflow.cfg

WORKDIR /opt/airflow
