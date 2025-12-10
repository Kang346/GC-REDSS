#!/bin/bash
# Quick start script for GC-REDSS

echo "=========================================="
echo "GC-REDSS - Quick Start"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Build and start containers
echo "Building and starting Docker containers..."
docker-compose up --build -d

echo ""
echo "=========================================="
echo "JupyterLab is starting..."
echo "Access it at: http://localhost:8888"
echo "=========================================="
echo ""
echo "To stop the containers, run: docker-compose down"
