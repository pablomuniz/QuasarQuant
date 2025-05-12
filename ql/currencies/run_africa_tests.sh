#!/bin/bash

# Script to compare QuantLib C++ currency data with Mojo implementation.

PROJECT_ROOT="/app" # Assuming this is the root inside Docker containing 'quantfork'

echo "Changing to project root: ${PROJECT_ROOT}"
cd "${PROJECT_ROOT}" || exit 1 # cd back to /app first

# Define paths relative to PROJECT_ROOT (current directory)
CPP_SOURCE_FILE="quantfork/ql/currencies/test_cpp_africa_runner.cpp" # Path relative to /app
CPP_RUNNER_PATH="./test_cpp_africa_runner" # Runner executable in /app
MOJO_RUNNER_SOURCE="quantfork/ql/currencies/africa_runner.mojo" # Source path relative to /app
MOJO_RUNNER_PATH="./africa_mojo_runner"   # Runner executable in /app

# --- Compilation (Run from project root /app) ---

echo "Compiling C++ test runner..."
# Adjust include/lib paths for QuantLib as needed for your Docker image
# Ensure QuantLib headers and libraries are available
g++ -std=c++17 -I./quantfork -I/usr/local/include "${CPP_SOURCE_FILE}" -o "${CPP_RUNNER_PATH}" -L/usr/local/lib -lQuantLib -pthread
if [ $? -ne 0 ]; then
    echo "C++ compilation failed!"
    exit 1
fi
echo "C++ compilation successful."

echo "Compiling Mojo test runner..."
# Compile the runner which imports from the africa definitions file
mojo build "${MOJO_RUNNER_SOURCE}" -o "${MOJO_RUNNER_PATH}"
if [ $? -ne 0 ]; then
    echo "Mojo compilation failed!"
    exit 1
fi
echo "Mojo compilation successful. Mojo runner at: ${MOJO_RUNNER_PATH}"


# --- Test Cases --- 
# List of currency codes defined in africa.mojo
currency_codes_to_test=("AOA" "BWP" "EGP" "ETB" "GHS" "KES" "MAD" "MUR" "NGN" "TND" "UGX" "XOF" "ZAR" "ZMW")

echo ""
echo "Running Currency Data Tests..."

passed_count=0
failed_count=0

for code in "${currency_codes_to_test[@]}"; do
    echo ""
    echo "Test: Currency ${code}"

    # Run C++ runner (Paths are relative to current dir /app)
    cpp_out=$("${CPP_RUNNER_PATH}" "${code}" 2>&1)
    cpp_exit_code=$?
    echo "  CPP Output (Exit: ${cpp_exit_code}):"
    echo "---"
    echo "${cpp_out}"
    echo "---"
    
    # Run Mojo runner (Paths are relative to current dir /app)
    mojo_out=$("${MOJO_RUNNER_PATH}" "${code}" 2>&1)
    mojo_exit_code=$?
    echo "  Mojo Output (Exit: ${mojo_exit_code}):"
    echo "---"
    echo "${mojo_out}"
    echo "---"

    # Check exit codes first
    if [ "${cpp_exit_code}" -ne 0 ]; then
        echo "  RESULT: FAIL (C++ runner failed for ${code})"
        failed_count=$((failed_count + 1))
        continue
    fi
    if [ "${mojo_exit_code}" -ne 0 ]; then
        echo "  RESULT: FAIL (Mojo runner failed for ${code})"
        failed_count=$((failed_count + 1))
        continue
    fi 

    # Compare outputs (exact string comparison for the whole block)
    if [ "${cpp_out}" == "${mojo_out}" ]; then
        echo "  RESULT: PASS"
        passed_count=$((passed_count + 1))
    else
        echo "  RESULT: FAIL (Outputs differ for ${code})"
        echo "    Diff:"
        diff <(echo "${cpp_out}") <(echo "${mojo_out}") | sed 's/^/    /'
        failed_count=$((failed_count + 1))
    fi
done

echo ""
echo "--- Test Summary --- "
echo "Currencies Tested: ${#currency_codes_to_test[@]}"
echo "Passed: ${passed_count}"
echo "Failed: ${failed_count}"

if [ "${failed_count}" -ne 0 ]; then
    exit 1
fi
exit 0 