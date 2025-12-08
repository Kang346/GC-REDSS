FROM jupyter/pyspark-notebook:latest

# Set working directory
WORKDIR /home/jovyan/work

# Install system dependencies for geospatial libraries
USER root
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Switch back to jovyan user
USER jovyan

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose Jupyter port
EXPOSE 8888

# Start JupyterLab
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--NotebookApp.token=''", "--NotebookApp.password=''"]
