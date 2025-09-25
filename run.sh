#!/bin/bash

# ISI Macroscope Control System - Unified Launcher
# Starts both backend and frontend from the codebase root

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_DIR="./backend"
FRONTEND_DIR="./frontend"
LOG_DIR="./logs"

# Parse command line arguments
MODE="production"
VERBOSE=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dev) MODE="development"; shift ;;
        --verbose) VERBOSE=true; shift ;;
        --help)
            echo "Usage: ./run.sh [options]"
            echo "Options:"
            echo "  --dev      Run in development mode"
            echo "  --verbose  Show detailed output"
            echo "  --help     Show this help message"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   ISI Macroscope Control System Launcher   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Mode: ${MODE}${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js found${NC}"

# Check Poetry (for backend)
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}✗ Poetry is not installed${NC}"
    echo "  Install with: pip install poetry"
    exit 1
fi
echo -e "${GREEN}✓ Poetry found${NC}"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"

    # Kill backend if running
    if [[ -n "$BACKEND_PID" ]]; then
        echo -e "${YELLOW}Stopping backend (PID: $BACKEND_PID)...${NC}"
        kill -TERM "$BACKEND_PID" 2>/dev/null || true
    fi

    # Kill frontend if running
    if [[ -n "$FRONTEND_PID" ]]; then
        echo -e "${YELLOW}Stopping frontend (PID: $FRONTEND_PID)...${NC}"
        kill -TERM "$FRONTEND_PID" 2>/dev/null || true
    fi

    echo -e "${GREEN}Shutdown complete${NC}"
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM EXIT

# Start Backend
echo ""
echo -e "${BLUE}Starting Backend...${NC}"
cd "$BACKEND_DIR"

# Install dependencies if needed
if [[ ! -d ".venv" ]]; then
    echo -e "${YELLOW}Installing backend dependencies...${NC}"
    poetry install
fi

# Start backend based on mode
if [[ "$MODE" == "development" ]]; then
    echo -e "${GREEN}Starting backend in development mode...${NC}"
    if [[ "$VERBOSE" == true ]]; then
        PYTHONPATH=src poetry run python src/isi_control/main.py --dev &
    else
        PYTHONPATH=src poetry run python src/isi_control/main.py --dev > "../$LOG_DIR/backend.log" 2>&1 &
    fi
else
    echo -e "${GREEN}Starting backend in production mode...${NC}"
    if [[ "$VERBOSE" == true ]]; then
        PYTHONPATH=src poetry run python src/isi_control/main.py &
    else
        PYTHONPATH=src poetry run python src/isi_control/main.py > "../$LOG_DIR/backend.log" 2>&1 &
    fi
fi

BACKEND_PID=$!
echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"

# Wait for backend to be ready
echo -e "${YELLOW}Waiting for backend to initialize...${NC}"
sleep 3

# Check if backend is still running
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo -e "${RED}✗ Backend failed to start${NC}"
    echo "Check logs at: $LOG_DIR/backend.log"
    exit 1
fi

# Start Frontend
echo ""
echo -e "${BLUE}Starting Frontend...${NC}"
cd "../$FRONTEND_DIR"

# Install dependencies if needed
if [[ ! -d "node_modules" ]]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    npm install
fi

# Start frontend based on mode
if [[ "$MODE" == "development" ]]; then
    echo -e "${GREEN}Starting frontend in development mode...${NC}"
    if [[ "$VERBOSE" == true ]]; then
        npm run dev &
    else
        npm run dev > "../$LOG_DIR/frontend.log" 2>&1 &
    fi
else
    echo -e "${GREEN}Starting frontend in production mode...${NC}"
    if [[ "$VERBOSE" == true ]]; then
        npm start &
    else
        npm start > "../$LOG_DIR/frontend.log" 2>&1 &
    fi
fi

FRONTEND_PID=$!
echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"

# Display status
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         System Successfully Started         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Backend PID:  $BACKEND_PID${NC}"
echo -e "${GREEN}Frontend PID: $FRONTEND_PID${NC}"
echo ""

if [[ "$VERBOSE" == false ]]; then
    echo "Logs:"
    echo "  Backend:  $LOG_DIR/backend.log"
    echo "  Frontend: $LOG_DIR/frontend.log"
    echo ""
fi

echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID