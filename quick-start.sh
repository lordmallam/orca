#!/bin/bash

echo "========================================"
echo "AIS Viewer System - Quick Start"
echo "========================================"
echo ""

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Error: Docker is required but not installed."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "Error: Docker Compose is required but not installed."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Error: Python 3 is required but not installed."; exit 1; }

echo "Prerequisites check passed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f backend/.env ]; then
    echo "Creating backend/.env file..."
    cp backend/.env.example backend/.env
    echo "Please edit backend/.env and add your AISSTREAM_API_KEY"
    echo ""
fi

# Start database
echo "Starting PostgreSQL database..."
docker-compose up -d
echo "Database started"
echo ""

# Wait for database to be ready
echo "Waiting for database to be ready..."
sleep 10
echo "Database ready"
echo ""

# Setup Python virtual environment
if [ ! -d backend/venv ]; then
    echo "Creating Python virtual environment..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
    echo "Python environment setup complete"
    echo ""
fi

echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit backend/.env and add your AISSTREAM_API_KEY"
echo "   Get one at: https://aisstream.io"
echo ""
echo "2. Start backend services:"
echo "   Terminal 1: cd backend && source venv/bin/activate && python ingest_service.py"
echo "   Terminal 2: cd backend && source venv/bin/activate && python api_service.py"
echo ""
echo "3. Setup mobile app:"
echo "   cd mobile"
echo "   npm install"
echo "   Create mobile/.env with EXPO_PUBLIC_API_BASE_URL and EXPO_PUBLIC_MAPBOX_TOKEN"
echo "   npm start"
echo ""
echo "4. Test the system:"
echo "   curl http://localhost:8000/health"
echo ""
echo "For more details, see README.md and DEPLOYMENT.md"
echo ""

