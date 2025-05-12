#!/bin/bash

# Script to compare QuantLib C++ currency data with Mojo implementation (Europe).

PROJECT_ROOT="/app" # Assuming this is the root inside Docker containing 'quantfork'

echo "Changing to project root: ${PROJECT_ROOT}"
cd "${PROJECT_ROOT}" || exit 1 # cd back to /app first

# Define paths relative to PROJECT_ROOT (current directory)
CPP_SOURCE_FILE="quantfork/ql/currencies/test_cpp_europe_runner.cpp" # Path relative to /app
CPP_RUNNER_PATH="./test_cpp_europe_runner" # Runner executable in /app
MOJO_RUNNER_SOURCE="quantfork/ql/currencies/europe_runner.mojo" # Source path relative to /app
MOJO_RUNNER_PATH="./europe_mojo_runner"   # Runner executable in /app

# --- Compilation (Run from project root /app) ---

echo "Compiling C++ test runner (Europe)..."
g++ -std=c++17 -I./quantfork -I/usr/local/include "${CPP_SOURCE_FILE}" -o "${CPP_RUNNER_PATH}" -L/usr/local/lib -lQuantLib -pthread
if [ $? -ne 0 ]; then
    echo "C++ compilation failed!"
    exit 1
fi
echo "C++ compilation successful."

echo "Compiling Mojo test runner (Europe)..."
mojo build "${MOJO_RUNNER_SOURCE}" -o "${MOJO_RUNNER_PATH}"
if [ $? -ne 0 ]; then
    echo "Mojo compilation failed!"
    exit 1
fi
echo "Mojo compilation successful. Mojo runner at: ${MOJO_RUNNER_PATH}"


# --- Test Cases --- 
# List of currency codes defined in europe.mojo
currency_codes_to_test=(
    "BGL" "BYR" "CHF" "CYP" "CZK" "DKK" "EEK" "EUR" "GBP" "HUF" \
    "ISK" "LTL" "LVL" "NOK" "PLN" "ROL" "RON" "RUB" "SEK" "SIT" \
    "TRL" "TRY" \
    "ATS" "BEF" "DEM" "ESP" "FIM" "FRF" "GRD" "IEP" "ITL" "LUF" \
    "MTL" "NLG" "PTE" "SKK" \
    "UAH" "RSD" "HRK" "BGN" "GEL"
)

echo ""
echo "Running Currency Data Tests (Europe)..."

passed_count=0
failed_count=0

for code in "${currency_codes_to_test[@]}"; do
    echo ""
    echo "Test: Currency ${code}"

    # Run C++ runner 
    cpp_out=$("${CPP_RUNNER_PATH}" "${code}" 2>&1)
    cpp_exit_code=$?
    echo "  CPP Output (Exit: ${cpp_exit_code}):"
    echo "---"
    echo "${cpp_out}"
    echo "---"
    
    # Run Mojo runner
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

    # Compare outputs
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
echo "--- Test Summary (Europe) --- "
echo "Currencies Tested: ${#currency_codes_to_test[@]}"
echo "Passed: ${passed_count}"
echo "Failed: ${failed_count}"

if [ "${failed_count}" -ne 0 ]; then
    exit 1
fi
exit 0 