#!/bin/bash

# Script to compare QuantLib C++ rounding with Mojo rounding implementation.

# Directories - adjust if your files are elsewhere relative to this script
CPP_RUNNER_PATH="./test_cpp_runner"
MOJO_FILE_PATH="./rounding.mojo"
MOJO_RUNNER_PATH="./rounding_mojo_runner"
CPP_SOURCE_FILE="./test_cpp_rounding_runner.cpp"

# --- Compilation (inside Docker where QuantLib is available) ---
# This assumes the script is run from a directory where QuantLib headers and libs are accessible.
# Typically, you'd run this script INSIDE your Docker dev container.

echo "Compiling C++ test runner..."
# Adjust include and lib paths if necessary for your Docker environment.
# -I/app/quantfork is for ql/math/rounding.hpp if it's not found via default system includes for QuantLib
# -I/usr/local/include is a common place for QuantLib headers if installed globally in image
# -L/usr/local/lib is a common place for libQuantLib.so
g++ -std=c++17 -I/app/quantfork -I/usr/local/include "${CPP_SOURCE_FILE}" -o "${CPP_RUNNER_PATH}" -L/usr/local/lib -lQuantLib -pthread
if [ $? -ne 0 ]; then
    echo "C++ compilation failed!"
    exit 1
fi
echo "C++ compilation successful."

echo ""
echo "Compiling Mojo test runner..."
mojo build "${MOJO_FILE_PATH}" -o "${MOJO_RUNNER_PATH}"
if [ $? -ne 0 ]; then
    echo "Mojo compilation failed!"
    exit 1
fi
echo "Mojo compilation successful."

# --- Test Cases --- 
# Format: "description" "type_str" precision digit value expected_cpp_approx(optional_for_comments_only)
readarray -t test_cases < <(cat <<EOF
"Closest 1.234 (prec 2, digit 5)" Closest 2 5 1.234
"Closest 1.235 (prec 2, digit 5)" Closest 2 5 1.235
"Closest 1.237 (prec 2, digit 5)" Closest 2 5 1.237
"Closest -1.235 (prec 2, digit 5)" Closest 2 5 -1.235
"Closest 1.000000000000001 (prec 14, digit 5)" Closest 14 5 1.000000000000001
"Closest 1.000000000000000 (prec 14, digit 5)" Closest 14 5 1.000000000000000
"Up 1.2 (prec 0, digit 5)" Up 0 5 1.2
"Up 1.0 (prec 0, digit 5)" Up 0 5 1.0
"Up -1.2 (prec 0, digit 5)" Up 0 5 -1.2
"Up 1.999 (prec 0, digit 5)" Up 0 5 1.999
"Down 1.2 (prec 0, digit 5)" Down 0 5 1.2
"Down 1.999 (prec 0, digit 5)" Down 0 5 1.999
"Down -1.2 (prec 0, digit 5)" Down 0 5 -1.2
"None 3.14159 (prec 2, digit 5)" None 2 5 3.14159
"QL Floor 1.235 (prec 2, digit 5)" Floor 2 5 1.235
"QL Floor 1.234 (prec 2, digit 5)" Floor 2 5 1.234
"QL Floor -1.235 (prec 2, digit 5)" Floor 2 5 -1.235
"QL Floor -1.237 (prec 2, digit 5)" Floor 2 5 -1.237
"QL Ceiling 1.235 (prec 2, digit 5)" Ceiling 2 5 1.235
"QL Ceiling 1.234 (prec 2, digit 5)" Ceiling 2 5 1.234
"QL Ceiling -1.235 (prec 2, digit 5)" Ceiling 2 5 -1.235
"QL Ceiling -1.237 (prec 2, digit 5)" Ceiling 2 5 -1.237
"Closest 0.0 (prec 2, digit 5)" Closest 2 5 0.0
"Up 0.0 (prec 0, digit 5)" Up 0 5 0.0
"Floor -0.000000000000001 (prec 14, digit 5)" Floor 14 5 -0.000000000000001
"Ceiling 0.000000000000001 (prec 14, digit 5)" Ceiling 14 5 0.000000000000001
EOF
)

echo ""
echo "Running tests..."

passed_count=0
failed_count=0

for test_case_line in "${test_cases[@]}"; do
    # Parse the test case line
    desc=$(echo "$test_case_line" | cut -d'"' -f2)
    params=$(echo "$test_case_line" | cut -d'"' -f3- | sed 's/^ //')
    type_str=$(echo "$params" | awk '{print $1}')
    precision=$(echo "$params" | awk '{print $2}')
    digit=$(echo "$params" | awk '{print $3}')
    value=$(echo "$params" | awk '{print $4}')

    echo ""
    echo "Test: ${desc}"
    echo "Params: Type=${type_str}, Precision=${precision}, Digit=${digit}, Value=${value}"

    cpp_out=$("${CPP_RUNNER_PATH}" "${type_str}" "${precision}" "${digit}" "${value}" 2>&1)
    cpp_exit_code=$?

    # Assuming you are in a Magic shell environment to run mojo
    mojo_out=$("${MOJO_RUNNER_PATH}" "${type_str}" "${precision}" "${digit}" "${value}" 2>&1)
    mojo_exit_code=$?
    
    # Trim whitespace for comparison if necessary, though direct comparison should work if formatting is identical.
    # cpp_out_trimmed=$(echo "${cpp_out}" | tr -d '[:space:]')
    # mojo_out_trimmed=$(echo "${mojo_out}" | tr -d '[:space:]')

    echo "  CPP Output: '${cpp_out}' (Exit: ${cpp_exit_code})"
    echo "  Mojo Output: '${mojo_out}' (Exit: ${mojo_exit_code})"

    if [ "${cpp_exit_code}" -ne 0 ]; then
        echo "  RESULT: FAIL (C++ runner failed)"
        failed_count=$((failed_count + 1))
        continue
    fi
    if [ "${mojo_exit_code}" -ne 0 ]; then
        echo "  RESULT: FAIL (Mojo runner failed)"
        failed_count=$((failed_count + 1))
        continue
    fi 

    # Using awk for float comparison with tolerance
    # This is more robust than direct string comparison for floats.
    comparison_result=$(awk -v cpp="${cpp_out}" -v mojo="${mojo_out}" \
        'BEGIN { diff = cpp - mojo; if (diff < 0) diff = -diff; if (diff < 0.000000000000001) print "PASS"; else print "FAIL" }')

    if [ "${comparison_result}" == "PASS" ]; then
        echo "  RESULT: PASS"
        passed_count=$((passed_count + 1))
    else
        echo "  RESULT: FAIL (Outputs differ)"
        failed_count=$((failed_count + 1))
    fi
done

echo ""
echo "--- Test Summary ---"
echo "Passed: ${passed_count}"
echo "Failed: ${failed_count}"

if [ "${failed_count}" -ne 0 ]; then
    exit 1
fi
exit 0 