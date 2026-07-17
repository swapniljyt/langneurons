#!/bin/bash

GREEN='\033[0;32m'
NC='\033[0m'
BLUE='\033[0;34m'

echo -e "${BLUE}=== Starting LangNeurons Console Server ===${NC}"

# Ensure redis is running (if installed locally)
if command -v redis-server &> /dev/null; then
    if ! systemctl is-active --quiet redis-server &> /dev/null && ! pgrep redis-server &> /dev/null; then
        echo -e "${BLUE}Starting Redis server...${NC}"
        redis-server --daemonize yes
    fi
fi

# Move into the frontend directory and run with the workspace virtualenv
cd frontend
../backend/venv/bin/python3 server.py
