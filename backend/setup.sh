#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

GREEN='\033[0;32m'
NC='\033[0;3m' # No Color
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'

echo -e "${BLUE}==============================================${NC}"
echo -e "${GREEN}      LangNeurons Setup & Installer           ${NC}"
echo -e "${BLUE}==============================================${NC}"

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed. Please install Python 3.9+ first.${NC}"
    exit 1
fi

# Check for apt (Debian/Ubuntu-specific setup)
if command -v apt-get &> /dev/null; then
    echo -e "${BLUE}[1/4] Checking and installing system dependencies (Redis & python3-venv)...${NC}"
    
    # Check if python3-venv is installed
    if ! python3 -m venv --help &> /dev/null; then
        echo -e "${YELLOW}python3-venv is missing. Installing python3-venv...${NC}"
        sudo apt-get update && sudo apt-get install -y python3-venv
    fi

    # Check if redis-server is installed
    if ! command -v redis-server &> /dev/null; then
        echo -e "${YELLOW}redis-server is missing. Installing redis-server...${NC}"
        sudo apt-get update && sudo apt-get install -y redis-server
    fi

    # Start and enable Redis if not active
    if ! systemctl is-active --quiet redis-server; then
        echo -e "${YELLOW}Starting Redis service...${NC}"
        sudo systemctl enable redis-server
        sudo systemctl start redis-server
    fi
else
    echo -e "${YELLOW}Skipping apt installation (non-Debian/Ubuntu system). Please ensure redis-server is running on port 6379.${NC}"
fi

# 2. Setup virtual environment
echo -e "${BLUE}[2/4] Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}Virtual environment 'venv' created successfully.${NC}"
else
    echo -e "${YELLOW}Virtual environment 'venv' already exists. Skipping creation.${NC}"
fi

# 3. Upgrade pip and install requirements
echo -e "${BLUE}[3/4] Installing Python dependencies...${NC}"
venv/bin/python3 -m pip install --upgrade pip
venv/bin/python3 -m pip install -r requirements.txt
echo -e "${GREEN}All Python packages installed successfully.${NC}"

# 4. Copy .env template
echo -e "${BLUE}[4/4] Setting up configuration files...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}Copied .env.example to .env. Please open .env and add your LLM API keys!${NC}"
else
    echo -e "${YELLOW}.env already exists. Skipping copy.${NC}"
fi

echo -e "${BLUE}==============================================${NC}"
echo -e "${GREEN} 🎉 LangNeurons Setup Completed Successfully!  ${NC}"
echo -e "${BLUE}==============================================${NC}"
echo -e "${GREEN}To run your swarm, please follow these steps:${NC}"
echo -e "${YELLOW}1. Edit the '.env' file to add your API keys (e.g. MOONSHOT_API_KEY, OPENAI_API_KEY, etc.)${NC}"
echo -e "${YELLOW}2. Build the swarm: ${GREEN}venv/bin/python3 entrypoints/run_agent_langneuron.py${NC}"
echo -e "${YELLOW}3. Execute the swarm: ${GREEN}venv/bin/python3 entrypoints/run_agent_langneuron.py --freeze${NC}"
echo -e "${BLUE}==============================================${NC}"
