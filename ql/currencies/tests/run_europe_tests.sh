#!/bin/bash

# Script to compare QuantLib C++ currency data with Mojo implementation (Europe).
# This script is expected to be in quantfork/ql/currencies/tests/
# and its runner source files (test_cpp_europe_runner.cpp, europe_runner.mojo)
# are also expected in this same directory.
# It will output structured data for each test item.

# --- Configuration ---
SCRIPT_FULL_PATH="${BASH_SOURCE[0]}"
ABS_SCRIPT_DIR=$(cd "$(dirname "$SCRIPT_FULL_PATH")" && pwd)

# PROJECT_ROOT is two levels up from ABS_SCRIPT_DIR (tests/ -> currencies/ -> ql/ -> quantfork/)
# Correcting: tests/ -> currencies/ (1) -> ql/ (2) -> quantfork/ (3)
PROJECT_ROOT=$(cd "$ABS_SCRIPT_DIR/../../.." && pwd) # ../.. from tests/ to ql/, then one more ../ to quantfork/

# Define paths for runner source files and compiled executables (in the same dir as this script)
CPP_SOURCE_FILE_NAME="test_cpp_europe_runner.cpp"
CPP_SOURCE_FILE_ABS="${ABS_SCRIPT_DIR}/${CPP_SOURCE_FILE_NAME}"
CPP_RUNNER_BASENAME="test_cpp_europe_runner_compiled"
CPP_RUNNER_PATH_ABS="${ABS_SCRIPT_DIR}/${CPP_RUNNER_BASENAME}"

MOJO_RUNNER_SOURCE_NAME="europe_runner.mojo"
MOJO_RUNNER_SOURCE_ABS="${ABS_SCRIPT_DIR}/${MOJO_RUNNER_SOURCE_NAME}"
MOJO_RUNNER_BASENAME="europe_mojo_runner_compiled"
MOJO_RUNNER_PATH_ABS="${ABS_SCRIPT_DIR}/${MOJO_RUNNER_BASENAME}"

# --- Source Shared Utilities ---
# Path to shared_test_utils.sh assuming it's in quantfork/test/
# This script (run_europe_tests.sh) is in quantfork/ql/currencies/tests/
SHARED_UTILS_PATH=$(cd "$ABS_SCRIPT_DIR/../../../test" && pwd)/shared_test_utils.sh 

if [ -f "$SHARED_UTILS_PATH" ]; then
    source "$SHARED_UTILS_PATH"
else
    echo "ERROR ($SCRIPT_FULL_PATH): Shared test utilities not found at $SHARED_UTILS_PATH" >&2
    exit 1
fi

# --- Script-level Pass/Fail Counters ---
pas_count_script=0
fail_count_script=0

# --- Compilation (Attempted once per script run) ---
COMPILATION_HAD_ERRORS=false

# C++ Compilation
CPP_OVERALL_COMPILE_OUTPUT=""
CPP_OVERALL_COMPILE_EXIT_CODE=0
if [ -f "${CPP_SOURCE_FILE_ABS}" ]; then
    cpp_compile_output_log=$(mktemp)
    g++ -std=c++17 -I"${PROJECT_ROOT}" -I/usr/local/include "${CPP_SOURCE_FILE_ABS}" -o "${CPP_RUNNER_PATH_ABS}" -L/usr/local/lib -lQuantLib -pthread > "$cpp_compile_output_log" 2>&1
    CPP_OVERALL_COMPILE_EXIT_CODE=$?
    CPP_OVERALL_COMPILE_OUTPUT=$(cat "$cpp_compile_output_log")
    rm "$cpp_compile_output_log"
else
    CPP_OVERALL_COMPILE_OUTPUT="ERROR: C++ source file ${CPP_SOURCE_FILE_ABS} not found."
    CPP_OVERALL_COMPILE_EXIT_CODE=1
fi
if [ "${CPP_OVERALL_COMPILE_EXIT_CODE}" -ne 0 ]; then
    echo "INITIAL C++ COMPILATION FAILED:"
    echo "------------------------------------"
    echo "${CPP_OVERALL_COMPILE_OUTPUT}"
    echo "------------------------------------"
    COMPILATION_HAD_ERRORS=true
fi

# Mojo Compilation
MOJO_OVERALL_COMPILE_OUTPUT=""
MOJO_OVERALL_COMPILE_EXIT_CODE=0
if [ -f "${MOJO_RUNNER_SOURCE_ABS}" ]; then
    mojo_compile_output_log=$(mktemp)
    (cd "${PROJECT_ROOT}" && mojo build "${MOJO_RUNNER_SOURCE_ABS}" -o "${MOJO_RUNNER_PATH_ABS}") > "$mojo_compile_output_log" 2>&1
    MOJO_OVERALL_COMPILE_EXIT_CODE=$?
    MOJO_OVERALL_COMPILE_OUTPUT=$(cat "$mojo_compile_output_log")
    rm "$mojo_compile_output_log"
else
    MOJO_OVERALL_COMPILE_OUTPUT="ERROR: Mojo source file ${MOJO_RUNNER_SOURCE_ABS} not found."
    MOJO_OVERALL_COMPILE_EXIT_CODE=1
fi
if [ "${MOJO_OVERALL_COMPILE_EXIT_CODE}" -ne 0 ]; then
    echo "INITIAL MOJO COMPILATION FAILED:"
    echo "------------------------------------"
    echo "${MOJO_OVERALL_COMPILE_OUTPUT}"
    echo "------------------------------------"
    COMPILATION_HAD_ERRORS=true
fi

# --- Test Cases (List of currency codes) ---
currency_codes_to_test=(
    "BGL" "BYR" "CHF" "CYP" "CZK" "DKK" "EEK" "EUR" "GBP" "HUF" \
    "ISK" "LTL" "LVL" "NOK" "PLN" "ROL" "RON" "RUB" "SEK" "SIT" \
    "TRL" "TRY" \
    "ATS" "BEF" "DEM" "ESP" "FIM" "FRF" "GRD" "IEP" "ITL" "LUF" \
    "MTL" "NLG" "PTE" "SKK" \
    "UAH" "RSD" "HRK" "BGN" "GEL"
)

for code in "${currency_codes_to_test[@]}"; do
    TEST_ITEM_ID_VAL="europe_currency_${code}"
    DESCRIPTION_VAL="Test for European currency ${code} (via ${SCRIPT_FULL_PATH})"
    OVERALL_STATUS_VAL="FAIL" # Default to FAIL
    FAIL_REASON_VAL=""
    
    CPP_RUN_EXIT_CODE_VAL="N/A"
    CPP_STDOUT_VAL=""
    CPP_STDERR_VAL=""
    MOJO_RUN_EXIT_CODE_VAL="N/A"
    MOJO_STDOUT_VAL=""
    MOJO_STDERR_VAL=""
    DIFF_OUTPUT_VAL=""

    # Check C++ Compilation status (using overall status)
    if [ "${CPP_OVERALL_COMPILE_EXIT_CODE}" -ne 0 ]; then
        FAIL_REASON_VAL="C++ Compilation Failed (see initial error)"
    elif [ ! -f "${CPP_RUNNER_PATH_ABS}" ] || [ ! -x "${CPP_RUNNER_PATH_ABS}" ]; then
        FAIL_REASON_VAL="C++ Runner Not Found or Not Executable Post-Compile (see initial error for details)"
    else
        # C++ Compiled successfully, Run C++ runner
        cpp_out_temp=$(mktemp)
        cpp_err_temp=$(mktemp)
        "${CPP_RUNNER_PATH_ABS}" "${code}" > "$cpp_out_temp" 2> "$cpp_err_temp"
        CPP_RUN_EXIT_CODE_VAL=$?
        CPP_STDOUT_VAL=$(cat "$cpp_out_temp")
        CPP_STDERR_VAL=$(cat "$cpp_err_temp")
        rm "$cpp_out_temp" "$cpp_err_temp"

        if [ "${CPP_RUN_EXIT_CODE_VAL}" -ne 0 ]; then
            FAIL_REASON_VAL="C++ Runner Failed (Exit: ${CPP_RUN_EXIT_CODE_VAL})"
        fi
    fi

    # Proceed to Mojo only if C++ part hasn't set a fatal FAIL_REASON_VAL yet
    if [ -z "$FAIL_REASON_VAL" ]; then
        if [ "${MOJO_OVERALL_COMPILE_EXIT_CODE}" -ne 0 ]; then
            FAIL_REASON_VAL="Mojo Compilation Failed (see initial error)"
        elif [ ! -f "${MOJO_RUNNER_PATH_ABS}" ] || [ ! -x "${MOJO_RUNNER_PATH_ABS}" ]; then
            FAIL_REASON_VAL="Mojo Runner Not Found or Not Executable Post-Compile (see initial error for details)"
        else
            # Mojo Compiled successfully, Run Mojo runner
            mojo_out_temp=$(mktemp)
            mojo_err_temp=$(mktemp)
            "${MOJO_RUNNER_PATH_ABS}" "${code}" > "$mojo_out_temp" 2> "$mojo_err_temp"
            MOJO_RUN_EXIT_CODE_VAL=$?
            MOJO_STDOUT_VAL=$(cat "$mojo_out_temp")
            MOJO_STDERR_VAL=$(cat "$mojo_err_temp")
            rm "$mojo_out_temp" "$mojo_err_temp"

            if [ "${MOJO_RUN_EXIT_CODE_VAL}" -ne 0 ]; then
                FAIL_REASON_VAL="Mojo Runner Failed (Exit: ${MOJO_RUN_EXIT_CODE_VAL})"
            fi
        fi
    fi
    
    # Final status determination if no fatal errors so far
    if [ -z "$FAIL_REASON_VAL" ]; then
        if [ "${CPP_RUN_EXIT_CODE_VAL}" -eq 0 ] && [ "${MOJO_RUN_EXIT_CODE_VAL}" -eq 0 ]; then
            if [ "${CPP_STDOUT_VAL}" == "${MOJO_STDOUT_VAL}" ]; then
                OVERALL_STATUS_VAL="PASS"
            else
                FAIL_REASON_VAL="Outputs Differ"
                DIFF_OUTPUT_VAL=$(diff <(echo -n "${CPP_STDOUT_VAL}") <(echo -n "${MOJO_STDOUT_VAL}") 2>&1 || true)
                if [ -z "$DIFF_OUTPUT_VAL" ] && [ "${CPP_STDOUT_VAL}" != "${MOJO_STDOUT_VAL}" ]; then
                    DIFF_OUTPUT_VAL="Outputs differ, but diff command produced no specific output. STDOUTs:\nCPP: '${CPP_STDOUT_VAL}'\nMOJO: '${MOJO_STDOUT_VAL}'"
                fi
            fi
        else
            FAIL_REASON_VAL="Runner Failure Not Captured Correctly (CPP Exit: ${CPP_RUN_EXIT_CODE_VAL}, Mojo Exit: ${MOJO_RUN_EXIT_CODE_VAL})"
        fi
    fi

    # Update script-level counters
    if [ "$OVERALL_STATUS_VAL" == "PASS" ]; then
        pas_count_script=$((pas_count_script + 1))
    else
        fail_count_script=$((fail_count_script + 1))
    fi

    # --- Use shared functions to print the structured block ---
    print_test_item_kv "TEST_SCRIPT_NAME" "$SCRIPT_FULL_PATH"
    print_test_item_kv "TEST_ITEM_ID" "$TEST_ITEM_ID_VAL"
    print_test_item_kv "DESCRIPTION" "$DESCRIPTION_VAL"
    print_test_item_kv "OVERALL_STATUS" "$OVERALL_STATUS_VAL"
    if [ "$OVERALL_STATUS_VAL" == "FAIL" ]; then
        print_test_item_kv "FAIL_REASON" "$FAIL_REASON_VAL"
    fi

    print_test_item_kv "CPP_EXIT_CODE" "$CPP_RUN_EXIT_CODE_VAL"
    print_test_item_ml_begin "CPP_STDOUT_BEGIN"
    print_test_item_ml_content "$CPP_STDOUT_VAL"
    print_test_item_ml_end "CPP_STDOUT_END"
    print_test_item_ml_begin "CPP_STDERR_BEGIN"
    print_test_item_ml_content "$CPP_STDERR_VAL"
    print_test_item_ml_end "CPP_STDERR_END"

    print_test_item_kv "MOJO_EXIT_CODE" "$MOJO_RUN_EXIT_CODE_VAL"
    print_test_item_ml_begin "MOJO_STDOUT_BEGIN"
    print_test_item_ml_content "$MOJO_STDOUT_VAL"
    print_test_item_ml_end "MOJO_STDOUT_END"
    print_test_item_ml_begin "MOJO_STDERR_BEGIN"
    print_test_item_ml_content "$MOJO_STDERR_VAL"
    print_test_item_ml_end "MOJO_STDERR_END"

    if [ -n "$DIFF_OUTPUT_VAL" ] && [ "$OVERALL_STATUS_VAL" == "FAIL" ]; then
        print_test_item_ml_begin "DIFF_OUTPUT_BEGIN"
        print_test_item_ml_content "$DIFF_OUTPUT_VAL"
        print_test_item_ml_end "DIFF_OUTPUT_END"
    fi
    
    print_test_item_end_marker
    echo # For readability of raw output
done

# --- Use shared function to Print Script Summary ---
print_run_script_summary "${SCRIPT_FULL_PATH}" "${#currency_codes_to_test[@]}" "${pas_count_script}" "${fail_count_script}"

if [ "${fail_count_script}" -gt 0 ] || [ "${COMPILATION_HAD_ERRORS}" = true ] ; then
    exit 1
fi
exit 0 