@echo off
REM Quick start script for GC-REDSS (Windows)

echo ==========================================
echo GC-REDSS - Quick Start
echo ==========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not running. Please start Docker first.
    exit /b 1
)

REM Build and start containers
echo Building and starting Docker containers...
docker-compose up --build -d

echo.
echo ==========================================
echo JupyterLab is starting...
echo Access it at: http://localhost:8888
echo ==========================================
echo.
echo To stop the containers, run: docker-compose down

pause
