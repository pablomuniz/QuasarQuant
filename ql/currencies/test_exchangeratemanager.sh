#!/bin/bash

# Exit on any error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo "Building and running ExchangeRateManager tests..."

# Compile C++ test
echo "Compiling C++ test..."
g++ -std=c++17 -I. -I/usr/include -L/usr/lib test_exchangeratemanager.cpp -o test_exchangeratemanager_cpp -lQuantLib

# Compile Mojo test
echo "Compiling Mojo test..."
mojo test_exchangeratemanager.mojo -o test_exchangeratemanager_mojo
if [ $? -ne 0 ]; then
    echo -e "${RED}Mojo compilation failed${NC}"
    exit 1
fi

# Run both tests and capture output
echo -e "\n${BLUE}Running tests:${NC}"
echo -e "${GREEN}C++ Implementation:${NC}"
./test_exchangeratemanager_cpp > cpp_output.txt

echo -e "\n${GREEN}Mojo Implementation:${NC}"
# Run Mojo test and capture output
./test_exchangeratemanager_mojo > mojo_output.txt 2> mojo_error.txt
mojo_exit_code=$?

if [ $mojo_exit_code -ne 0 ]; then
    echo -e "${RED}Mojo program failed with exit code $mojo_exit_code${NC}"
    echo -e "${RED}Error output:${NC}"
    cat mojo_error.txt
    exit 1
fi

# Compare outputs
echo -e "\n${BLUE}Comparing outputs:${NC}"
if diff -q cpp_output.txt mojo_output.txt > /dev/null; then
    echo -e "\n${BOLD}${GREEN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                                                            ║"
    echo "║                         PASS                               ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
else
    echo -e "\n${BOLD}${RED}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                                                            ║"
    echo "║                         FAIL                               ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "Differences:"
    diff -u cpp_output.txt mojo_output.txt
fi

# Clean up
rm -f test_exchangeratemanager_cpp test_exchangeratemanager_mojo cpp_output.txt mojo_output.txt mojo_error.txt

echo -e "\n${GREEN}Done!${NC}" 