#!/bin/bash

# run_date_tests.sh

# Setup: Adjust paths as necessary
CPP_RUNNER="./test_cpp_date_runner"
MOJO_RUNNER_SRC="./date.mojo"
MOJO_RUNNER_EXE="./date_runner_mojo_exe" # mojo build output name

# --- Compilation ---
echo "Compiling C++ date runner (test_cpp_date_runner.cpp)..."
# You may need to adjust QL_CFLAGS and QL_LIBS if QuantLib is not in standard paths
# Example: export QL_CFLAGS="-I/path/to/quantlib/include"
# Example: export QL_LIBS="-L/path/to/quantlib/lib -lQuantLib"
# On Arch, if quantlib is installed via pacman, it might just work.
g++ test_cpp_date_runner.cpp -o $CPP_RUNNER -lQuantLib -std=c++17
if [ $? -ne 0 ]; then
    echo "C++ compilation failed! Exiting."
    exit 1
fi
echo "C++ compilation successful."

echo "Compiling Mojo date runner (date.mojo)..."
mojo build $MOJO_RUNNER_SRC -o $MOJO_RUNNER_EXE
if [ $? -ne 0 ]; then
    echo "Mojo compilation failed! Exiting."
    exit 1
fi
echo "Mojo compilation successful."

# --- Test Execution ---
total_tests=0
passed_tests=0

# Function to run a single test case
# Args: <test_name_for_display> <command_and_args_for_runners_as_string>
run_test() {
    local test_name="$1"
    local runner_args_str="$2"

    total_tests=$((total_tests + 1))
    echo -n "Test: $test_name ... "

    read -r -a runner_args <<< "$runner_args_str" # Split string into array

    # Temporary files for output
    local cpp_out_file="cpp_runner_out.tmp"
    local mojo_out_file="mojo_runner_out.tmp"

    # Run C++ runner and capture exit code and output
    $CPP_RUNNER "${runner_args[@]}" > "${cpp_out_file}" 2>&1
    cpp_exit_code=$?
    cpp_output=$(cat "${cpp_out_file}")

    # Run Mojo runner and capture exit code and output
    $MOJO_RUNNER_EXE "${runner_args[@]}" > "${mojo_out_file}" 2>&1
    mojo_exit_code=$?
    mojo_output=$(cat "${mojo_out_file}")

    # Clean up temp files
    rm -f "${cpp_out_file}" "${mojo_out_file}"
    
    local test_passed=0 # 0 for pass, 1 for fail

    if [ ${cpp_exit_code} -eq 1 ] && [ ${mojo_exit_code} -ne 0 ]; then
        # C++ exited with 1 (expected QL error), and Mojo also exited with an error.
        # This is considered a PASS for tests designed to fail with invalid inputs.
        echo "PASS (Both runners indicated an error: CPP=${cpp_exit_code}, Mojo=${mojo_exit_code})"
        # Optionally, if you want to ensure Mojo's error message matches C++'s for these cases:
        # diff_output=$(diff <(echo "${cpp_output}") <(echo "${mojo_output}"))
        # if [ -n "${diff_output}" ]; then
        #     echo "  Note: Error messages differ."
        #     echo "$diff_output" | sed 's/^/    /'
        # fi
        test_passed=1
    elif [ ${cpp_exit_code} -ne ${mojo_exit_code} ]; then
        echo "FAIL (Exit codes differ: CPP=${cpp_exit_code}, Mojo=${mojo_exit_code})"
        test_passed=0
    elif [ ${cpp_exit_code} -eq 0 ]; then # Both exited with 0, compare stdout
        diff_output=$(diff <(echo "${cpp_output}") <(echo "${mojo_output}"))
        if [ -z "${diff_output}" ]; then
            echo "PASS"
            test_passed=1
        else
            echo "FAIL (Outputs differ for exit code 0)"
            # diff_result is already set from above
            test_passed=0
        fi
    else
        # Both exited with the same non-zero, non-1 (for C++) code. This is an unexpected error state.
        echo "FAIL (Both runners failed with unexpected exit codes: CPP=${cpp_exit_code}, Mojo=${mojo_exit_code})"
        test_passed=0
    fi

    if [ ${test_passed} -eq 1 ]; then
        passed_tests=$((passed_tests + 1))
    else
        # Detailed output for failures
        echo "  Runner Args: $runner_args_str"
        echo "  CPP Exit Code: $cpp_exit_code"
        echo "  CPP Output:"
        echo "$cpp_output" | sed 's/^/    /'
        echo "  Mojo Exit Code: $mojo_exit_code"
        echo "  Mojo Output:"
        echo "$mojo_output" | sed 's/^/    /'
        # Re-calculate diff if not already done in a failing path, or if it was from a non-0 exit code path
        if ! ([ ${cpp_exit_code} -eq 0 ] && [ ${mojo_exit_code} -eq 0 ]); then 
             diff_output=$(diff <(echo "${cpp_output}") <(echo "${mojo_output}"))
        fi
        if [ -n "$diff_output" ]; then
            echo "  Diff:"
            echo "$diff_output" | sed 's/^/    /'
        fi
        # Optional: exit on first failure
        # exit 1 
    fi
}

echo ""
echo "--- Running Date Tests ---"

# Test Cases (Commands are the same for both runners)
# Weekday reminder: Sunday=1, Monday=2, ..., Saturday=7

# 1. Construction & Basic Inspection
run_test "Inspect Jan 1, 1901 (DMY)" "inspect_dmy 1 1 1901"
run_test "Inspect Dec 31, 2199 (DMY)" "inspect_dmy 31 12 2199"
run_test "Inspect Feb 29, 2024 (Leap)" "inspect_dmy 29 2 2024"
run_test "Inspect Feb 28, 2023 (Non-Leap)" "inspect_dmy 28 2 2023"
run_test "Inspect Serial 367" "inspect_serial 367"
run_test "Inspect Serial 109574" "inspect_serial 109574"
run_test "Inspect Serial 0 (Null Date)" "inspect_serial 0"
run_test "Inspect Invalid DMY (31 Apr 2024)" "inspect_dmy 31 4 2024" 
run_test "Inspect Invalid DMY (Feb 30 2023)" "inspect_dmy 30 2 2023"
run_test "Inspect Invalid DMY (Feb 31 2024)" "inspect_dmy 31 2 2024"
run_test "Inspect Invalid DMY (Jan 1 1900)" "inspect_dmy 1 1 1900"
run_test "Inspect Invalid DMY (Jan 1 2200)" "inspect_dmy 1 1 2200"
run_test "Inspect Invalid DMY (1 Jan 13 2023)" "inspect_dmy 1 13 2023"


# 2. toString()
run_test "toString Jan 1, 1901 (DMY)" "toString_dmy 1 1 1901"
run_test "toString July 26, 2024 (DMY)" "toString_dmy 26 7 2024"
run_test "toString Serial 0 (Null Date)" "toString_serial 0"
run_test "toString Serial 45400 (Apr 18, 2024)" "toString_serial 45400" # Corrected date for serial
run_test "toString Invalid DMY (31 Apr 2024)" "toString_dmy 31 4 2024"
run_test "toString_dmy 31 12 2199" "toString_dmy 31 12 2199"
run_test "toString_dmy 29 2 2000" "toString_dmy 29 2 2000"
run_test "toString_dmy 28 2 2100" "toString_dmy 28 2 2100"
run_test "toString_dmy 5 3 1999" "toString_dmy 5 3 1999"

# 3. isEndOfMonth()
run_test "isEOM Jan 31, 2024 (DMY)" "isEndOfMonth_dmy 31 1 2024"
run_test "isEOM Jan 30, 2024 (DMY)" "isEndOfMonth_dmy 30 1 2024"
run_test "isEOM Feb 29, 2024 (DMY, Leap)" "isEndOfMonth_dmy 29 2 2024"
run_test "isEOM Feb 28, 2023 (DMY, Non-Leap)" "isEndOfMonth_dmy 28 2 2023"
run_test "isEOM Serial 0 (Null)" "isEndOfMonth_serial 0"
run_test "isEOM Serial for Feb 28, 2023 (44985)" "isEndOfMonth_serial 44985" # Corrected serial
run_test "isEOM Invalid DMY (31 Apr 2024)" "isEndOfMonth_dmy 31 4 2024"
run_test "isEndOfMonth_dmy 31 12 2199" "isEndOfMonth_dmy 31 12 2199"
run_test "isEndOfMonth_dmy 29 2 2000" "isEndOfMonth_dmy 29 2 2000"
run_test "isEndOfMonth_dmy 28 2 2100" "isEndOfMonth_dmy 28 2 2100"
run_test "isEndOfMonth_dmy 30 4 2024" "isEndOfMonth_dmy 30 4 2024"
run_test "isEndOfMonth_dmy 28 2 2000" "isEndOfMonth_dmy 28 2 2000"
run_test "isEndOfMonth_dmy 29 2 1901" "isEndOfMonth_dmy 29 2 1901" # Invalid day

# 4. nextWeekday()
run_test "nextWD Mon(22/7/24) -> Fri(6)" "nextWeekday_dmy 22 7 2024 6"
run_test "nextWD Fri(26/7/24) -> Mon(2)" "nextWeekday_dmy 26 7 2024 2"
run_test "nextWD Fri(26/7/24) -> Fri(6) (same day)" "nextWeekday_dmy 26 7 2024 6" # Corrected expectation
run_test "nextWD Sun(28/7/24) -> Tue(3)" "nextWeekday_dmy 28 7 2024 3"
run_test "nextWD Serial 0 (Null) -> Mon(2)" "nextWeekday_serial 0 2"
run_test "nextWD Invalid DMY (31 Apr 2024) -> Mon(2)" "nextWeekday_dmy 31 4 2024 2"
run_test "nextWD Thu(28/12/23) -> Fri(6)" "nextWeekday_dmy 28 12 2023 5"
run_test "nextWD Fri(29/12/23) -> Mon(2) (New Year)" "nextWeekday_dmy 29 12 2023 2"
run_test "nextWD Tue(27/2/24) -> Wed(4)" "nextWeekday_dmy 27 2 2024 4"
run_test "nextWD Wed(28/2/24) -> Thu(5) (Leap)" "nextWeekday_dmy 28 2 2024 5"

# 5. nthWeekday()
run_test "nthWD 1st Fri(6) July 2024" "nthWeekday 1 6 7 2024"
run_test "nthWD 3rd Mon(2) July 2024" "nthWeekday 3 2 7 2024"
run_test "nthWD 5th Sun(1) July 2024" "nthWeekday 5 1 7 2024" # (July 28th)
run_test "nthWD 5th Wed(4) July 2024" "nthWeekday 5 4 7 2024" # (July 31st)
run_test "nthWD 5th Fri(6) July 2024 (Non-existent)" "nthWeekday 5 6 7 2024"
run_test "nthWD 1st Mon(2) March 2023" "nthWeekday 1 2 3 2023"
run_test "nthWD 4th Thu(5) Nov 2023 (Thanksgiving)" "nthWeekday 4 5 11 2023"
run_test "nthWD 0th Fri(6) July 2024 (Invalid n)" "nthWeekday 0 6 7 2024"
run_test "nthWD 1st Fri(6) Invalid Month(13) 2024" "nthWeekday 1 6 13 2024"
run_test "nthWD 1st Invalid WD(8) July 2024" "nthWeekday 1 8 7 2024" # Known diff, Mojo is correct
run_test "nthWD 4th Fri(6) July 2024" "nthWeekday 4 6 7 2024"
run_test "nthWD 1st Sun(1) Jan 1901" "nthWeekday 1 1 1 1901"
run_test "nthWD 5th Mon(2) Feb 2024 (Non-existent)" "nthWeekday 5 2 2 2024"

# Additional serial tests
run_test "Inspect Serial 368 (Jan 2, 1901)" "inspect_serial 368"
run_test "Inspect Serial 109573 (Dec 30, 2199)" "inspect_serial 109573"

echo ""
echo "--- Test Summary ---"
echo "Total tests run: $total_tests"
echo "Passed tests:    $passed_tests"
failed_tests=$((total_tests - passed_tests))
echo "Failed tests:    $failed_tests"

if [ $failed_tests -eq 0 ]; then
    echo "All date tests PASSED!"
    exit 0
else
    echo "Some date tests FAILED."
    exit 1
fi 