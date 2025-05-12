#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../../.." # Project root is three levels up from script dir

# C++ Test Runner
CPP_RUNNER_SRC="${SCRIPT_DIR}/test_cpp_exchangeratemanager_runner.cpp"
CPP_RUNNER_EXE="${SCRIPT_DIR}/test_cpp_exchangeratemanager_runner" # Build executable in the same dir as script

# Mojo Test Runner
MOJO_RUNNER_SRC="${SCRIPT_DIR}/exchangeratemanager.mojo"
# MOJO_RUNNER_PKG_DIR is the directory that should be in MOJO_PACKAGE_PATH
MOJO_RUNNER_PKG_DIR="${PROJECT_ROOT}" # The directory containing 'quantfork' package
MOJO_EXECUTABLE="mojo" # Or path to mojo executable

# Output files (will be created in SCRIPT_DIR)
CPP_OUT="${SCRIPT_DIR}/cpp_erm_output.txt"
MOJO_OUT="${SCRIPT_DIR}/mojo_erm_output.txt"
DIFF_OUT="${SCRIPT_DIR}/diff_erm_output.txt"

# Function to compile C++ runner
compile_cpp() {
    echo "Compiling C++ ExchangeRateManager runner (in ${SCRIPT_DIR})..."
    # Adjust QL_INCLUDE_DIR and QL_LIB_DIR if QuantLib is installed in a non-standard location
    # For many systems, QuantLib headers are in /usr/include or /usr/local/include
    # and libraries in /usr/lib or /usr/local/lib
    # If using a local QuantLib build, point to its include and lib directories.
    # Example for a common setup:
    QL_INCLUDE_DIR="/usr/local/include" # FIXME: Replace with your QuantLib include path
    QL_LIB_DIR="/usr/local/lib"       # FIXME: Replace with your QuantLib lib path
    g++ -std=c++17 -I"${QL_INCLUDE_DIR}" "${CPP_RUNNER_SRC}" -o "${CPP_RUNNER_EXE}" -L"${QL_LIB_DIR}" -lQuantLib

    # For now, let's assume QuantLib is installed such that pkg-config can find it, or headers/libs are in default paths
    # This command relies on pkg-config being set up for QuantLib or QuantLib being in standard compiler paths.
    # If this fails, you'll need to specify -I and -L paths manually.
    # g++ -std=c++17 `pkg-config --cflags QuantLib` "${CPP_RUNNER_SRC}" -o "${CPP_RUNNER_EXE}" `pkg-config --libs QuantLib`
    echo "C++ compilation successful: ${CPP_RUNNER_EXE}"
}

# Function to run a single test and compare outputs
run_test() {
    local test_name="$1"
    shift # Remove test_name from arguments
    local cpp_args=("$@")
    local mojo_args=("$@") # Assuming mojo args are the same for now

    echo "----------------------------------------------------------------------"
    echo "RUNNING TEST: ${test_name}"
    echo "C++ ARGS: ${cpp_args[@]}"
    echo "MOJO ARGS: ${mojo_args[@]}"
    echo "----------------------------------------------------------------------"

    local cpp_exit_code=0
    "${CPP_RUNNER_EXE}" "${cpp_args[@]}" > "${CPP_OUT}" 2>&1 || cpp_exit_code=$?

    local mojo_exit_code=0
    # Ensure MOJO_PACKAGE_PATH includes the project root where quantfork package resides
    MOJO_PACKAGE_PATH="${MOJO_RUNNER_PKG_DIR}:${MOJO_PACKAGE_PATH}" "${MOJO_EXECUTABLE}" run "${MOJO_RUNNER_SRC}" "${mojo_args[@]}" > "${MOJO_OUT}" 2>&1 || mojo_exit_code=$?
    
    echo "C++ runner exited with code: $cpp_exit_code"
    echo "Mojo runner exited with code: $mojo_exit_code"

    if [ "$cpp_exit_code" -ne 0 ] && [ "$mojo_exit_code" -ne 0 ] && [ "$cpp_exit_code" -eq "$mojo_exit_code" ]; then
        echo "TEST ERRORED AS EXPECTED (both with code $cpp_exit_code): ${test_name}"
        # Consider if diffing error messages is useful or too noisy
        # if diff -u --strip-trailing-cr "${CPP_OUT}" "${MOJO_OUT}" > "${DIFF_OUT}"; then
        #    echo "Error messages are identical."
        # else
        #    echo "Error messages differ:"
        #    cat "${DIFF_OUT}"
        # fi
        return 0 # Success (expected error)
    elif [ "$cpp_exit_code" -ne 0 ] || [ "$mojo_exit_code" -ne 0 ]; then
        echo "TEST FAILED: ${test_name} - One of the runners failed or exited with non-zero code unexpectedly."
        echo "C++ Output (Exit Code: $cpp_exit_code):"
        cat "${CPP_OUT}"
        echo "Mojo Output (Exit Code: $mojo_exit_code):"
        cat "${MOJO_OUT}"
        return 1 # Failure
    fi 

    # Compare outputs if both exited successfully
    if diff -u --strip-trailing-cr "${CPP_OUT}" "${MOJO_OUT}" > "${DIFF_OUT}"; then
        echo "TEST PASSED: ${test_name}"
        return 0 # Success
    else
        echo "TEST FAILED: ${test_name}"
        echo "Diff output:"
        cat "${DIFF_OUT}"
        return 1 # Failure
    fi
}


# --- Main script execution ---

# Compile C++ runner
compile_cpp

# --- Define and run test cases ---
# Example test case structure:
# run_test "Test Name" <command_for_runner> <arg1> <arg2> ...

# Test 1: Inspect a known rate (EUR to USD on a specific date)
run_test "EUR/USD on 2023-01-05" inspect_known_rate EUR USD 5 1 2023

# Test 2: Inspect another known rate (GBP to JPY)
run_test "GBP/JPY on 2023-01-05" inspect_known_rate GBP JPY 5 1 2023

# Test 3: Triangulation via EUR (e.g. DEM to FRF, which are EMU currencies)
run_test "DEM/FRF on 1999-01-05 (EMU fixed)" inspect_known_rate DEM FRF 5 1 1999
run_test "DEM/USD on 1999-01-05 (Triangulation)" inspect_known_rate DEM USD 5 1 1999

# Test 4: Historical rates (e.g. TRL to USD)
run_test "TRL/USD on 2004-12-30 (Pre-redenomination)" inspect_known_rate TRL USD 30 12 2004

# Test 5: Rate for TRY after redenomination
run_test "TRY/USD on 2005-01-05 (Post-redenomination)" inspect_known_rate TRY USD 5 1 2005


echo "----------------------------------------------------------------------"
echo "All ExchangeRateManager tests completed."
# rm -f "${CPP_OUT}" "${MOJO_OUT}" "${DIFF_OUT}"
# rm -f "${CPP_RUNNER_EXE}"

exit 0 