#!/bin/bash
# Script to start the Flask API server

echo "Starting GC-REDSS API Server..."
echo ""

# Activate virtual environment
source venv/bin/activate

# Check if port 5000 is available, if not use 5001
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 5000 is in use, using port 5001 instead"
    export FLASK_PORT=5001
else
    export FLASK_PORT=5000
fi

# Start the API server
python src/api.py




