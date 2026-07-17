#!/bin/bash
set -e

GREEN='\033[0;32m'
NC='\033[0m'
BLUE='\033[0;34m'

echo -e "${BLUE}=== Setup LangNeurons Workspace ===${NC}"

# Go into langneurons subdirectory and run setup.sh
cd langneurons
chmod +x setup.sh
./setup.sh

echo -e "${GREEN}=== Setup completed successfully! ===${NC}"
