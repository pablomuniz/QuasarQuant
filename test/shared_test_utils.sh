#!/bin/bash
# Shared shell utilities for test scripts to produce standardized structured output.

# --- Test Item Output Functions ---

# Prints a key-value pair for the current test item.
# Usage: print_test_item_kv "KEY" "Value"
print_test_item_kv() {
    if [ $# -ne 2 ]; then
        echo "ERROR (shared_test_utils.sh): print_test_item_kv requires 2 arguments (key, value). Got $#" >&2
        return 1
    fi
    echo "$1: $2"
}

# Prints the beginning marker for a multi-line value.
# Usage: print_test_item_ml_begin "MARKER_KEY_BEGIN" (e.g., "CPP_STDOUT_BEGIN")
print_test_item_ml_begin() {
    if [ $# -ne 1 ]; then
        echo "ERROR (shared_test_utils.sh): print_test_item_ml_begin requires 1 argument (marker_key_begin). Got $#" >&2
        return 1
    fi
    echo "$1"
}

# Prints the content of a multi-line value. Ensures content is printed as is.
# Usage: print_test_item_ml_content "<multi-line content>"
print_test_item_ml_content() {
    # Allow for missing argument, which means empty content.
    # printf is safer for arbitrary content, including empty strings or strings with special characters.
    printf '%s\n' "${1:-}" # Defaults to empty string if $1 is not provided
}

# Prints the end marker for a multi-line value.
# Usage: print_test_item_ml_end "MARKER_KEY_END" (e.g., "CPP_STDOUT_END")
print_test_item_ml_end() {
    if [ $# -ne 1 ]; then
        echo "ERROR (shared_test_utils.sh): print_test_item_ml_end requires 1 argument (marker_key_end). Got $#" >&2
        return 1
    fi
    echo "$1"
}

# Prints the standard end marker for a test item.
# Usage: print_test_item_end_marker
print_test_item_end_marker() {
    echo "END_OF_TEST_ITEM"
}

# --- Run Script Summary Output Functions ---

# Prints the summary for the calling test script.
# Usage: print_run_script_summary "/path/to/script.sh" <total_items> <passed_count> <failed_count>
print_run_script_summary() {
    if [ $# -ne 4 ]; then
        echo "ERROR (shared_test_utils.sh): print_run_script_summary requires 4 arguments. Got $#" >&2
        return 1
    fi
    local script_path="$1"
    local total_items="$2"
    local passed_items="$3"
    local failed_items="$4"

    echo "RUN_SCRIPT_SUMMARY_BEGIN"
    print_test_item_kv "Script Path" "${script_path}"
    print_test_item_kv "Items Tested" "${total_items}"
    print_test_item_kv "Passed" "${passed_items}"
    print_test_item_kv "Failed" "${failed_items}"
    echo "RUN_SCRIPT_SUMMARY_END"
}

# --- Test Item Variable Initialization ---
# This is more of a convention for calling scripts to implement.
# However, we can provide a function to unset common variables if scripts choose to use it.
# Example: 
# initialize_common_test_item_vars() {
#   unset OVERALL_STATUS_VAL FAIL_REASON_VAL 
#   unset CPP_RUN_EXIT_CODE_VAL CPP_STDOUT_VAL CPP_STDERR_VAL
#   unset MOJO_RUN_EXIT_CODE_VAL MOJO_STDOUT_VAL MOJO_STDERR_VAL DIFF_OUTPUT_VAL
#   # Set defaults if needed
#   OVERALL_STATUS_VAL="FAIL" # Default to FAIL
#   CPP_RUN_EXIT_CODE_VAL="N/A"
#   MOJO_RUN_EXIT_CODE_VAL="N/A"
# }

# It's often cleaner for the main test script to manage its own variable resets within its loop.

# Ensure the script can be sourced without executing anything directly.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "ERROR (shared_test_utils.sh): This script is intended to be sourced, not executed directly." >&2
    exit 1
fi 