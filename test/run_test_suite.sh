#!/usr/bin/env bash
set -eo pipefail

# Force immediate output (no buffering)
export PYTHONUNBUFFERED=1
stdbuf -o0 -e0 true

# Debug function
debug() {
    echo "[DEBUG] $*" >&2
}

# Check terminal environment
if [ -z "$TERM" ]; then
    export TERM=xterm-256color
    debug "TERM was not set, setting to xterm-256color"
fi

# Ensure we have a valid tty
if [ ! -t 0 ] || [ ! -t 1 ]; then
    echo "Error: This script requires an interactive terminal" >&2
    exit 1
fi

# Ensure gum is installed and working
if ! command -v gum >/dev/null 2>&1; then
    echo "Error: gum is not installed. Please install it to run the TUI." >&2
    echo "Installation instructions: https://github.com/charmbracelet/gum#installation" >&2
    exit 1
fi

# Test gum functionality
if ! gum style "Testing gum..." >/dev/null 2>&1; then
    echo "Error: gum is not working properly in this environment" >&2
    exit 1
fi

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)

debug "Script directory: $SCRIPT_DIR"
debug "Project root: $PROJECT_ROOT"

# Variables for the current test item being parsed
current_test_script_name=""
current_test_item_id=""
current_description=""
current_overall_status=""
current_fail_reason=""
current_cpp_exit_code=""
current_cpp_stdout=""
current_cpp_stderr=""
current_mojo_exit_code=""
current_mojo_stdout=""
current_mojo_stderr=""
current_diff_output=""

# State flags for multiline blocks
in_cpp_stdout=false
in_cpp_stderr=false
in_mojo_stdout=false
in_mojo_stderr=false
in_diff_output=false
in_run_summary=false

# Buffer for run summary
run_summary_buffer=""

# Counters for the current script run
script_total_items=0
script_passed_items=0
script_failed_items=0

reset_current_item_vars() {
    current_test_script_name="" # Though this might be set once per script
    current_test_item_id=""
    current_description=""
    current_overall_status=""
    current_fail_reason=""
    current_cpp_exit_code=""
    current_cpp_stdout=""
    current_cpp_stderr=""
    current_mojo_exit_code=""
    current_mojo_stdout=""
    current_mojo_stderr=""
    current_diff_output=""

    in_cpp_stdout=false
    in_cpp_stderr=false
    in_mojo_stdout=false
    in_mojo_stderr=false
    in_diff_output=false
    # Do not reset in_run_summary here
}

display_test_item_result() {
    if [[ -z "$current_test_item_id" ]]; then
        # Nothing to display if ID is missing
        return
    fi

    echo # Newline for spacing
    
    # Create a visually appealing header with test ID and description
    local header_content="Test Item: ${current_test_item_id}"
    [[ -n "$current_description" ]] && header_content+=$'\n'"Description: ${current_description}"
    
    gum style \
        --border double \
        --border-foreground cyan \
        --padding "1" \
        --margin "0 1" \
        --align center \
        --width 100 \
        "$header_content"

    script_total_items=$((script_total_items + 1))

    # Create status display with emoji and color
    if [[ "$current_overall_status" == "PASS" ]]; then
        gum style \
            --align center \
            --width 100 \
            --foreground green \
            --bold \
            "✓ PASS ✓"
        script_passed_items=$((script_passed_items + 1))
    else
        # For failures, create a more detailed status block
        local status_block
        status_block=$(
            gum join --vertical \
                "$(gum style --align center --width 100 --foreground red --bold "✗ FAIL ✗")" \
                "$(gum style --align center --width 100 --foreground yellow --italic "${current_fail_reason:-No failure reason provided}")"
        )
        echo "$status_block"
        script_failed_items=$((script_failed_items + 1))
        
        # Create side-by-side comparison for outputs
        local cpp_output_block_title="C++ Output (Exit: ${current_cpp_exit_code:-N/A})"
        local cpp_content
        printf -v cpp_content "STDOUT:\\n%s\\nSTDERR:\\n%s" "${current_cpp_stdout:-No STDOUT recorded}" "${current_cpp_stderr:-No STDERR recorded}"
        
        local cpp_output_block
        cpp_output_block=$(
            gum style \
                --border normal \
                --border-foreground blue \
                --margin "1" \
                --padding "1" \
                --width 50 \
                "$cpp_output_block_title" \
                "$(echo -e "${cpp_content}")"
        )

        local mojo_output_block_title="Mojo Output (Exit: ${current_mojo_exit_code:-N/A})"
        local mojo_content
        printf -v mojo_content "STDOUT:\\n%s\\nSTDERR:\\n%s" "${current_mojo_stdout:-No STDOUT recorded}" "${current_mojo_stderr:-No STDERR recorded}"
        
        local mojo_output_block
        mojo_output_block=$(
            gum style \
                --border normal \
                --border-foreground yellow \
                --margin "1" \
                --padding "1" \
                --width 50 \
                "$mojo_output_block_title" \
                "$(echo -e "${mojo_content}")"
        )

        # Join the output blocks side by side with a separator
        gum join --horizontal --align center "$cpp_output_block" "$mojo_output_block"

        # Show diff output if available
        if [[ -n "$current_diff_output" ]]; then
            local diff_output_trimmed="${current_diff_output%$'\n'}"
            gum style \
                --border double \
                --border-foreground white \
                --margin "1" \
                --padding "1" \
                --align left \
                --width 100 \
                "Differences Found:" \
                "$(echo -e "${diff_output_trimmed}")"
        fi
    fi
    echo # Newline for spacing
}

discover_test_categories() {
    debug "Discovering test categories..."
    local categories=()
    while IFS= read -r -d '' dir; do
        if find "$dir" -type f \( -name "*_tests.sh" -o -name "test_*.sh" -o -name "run_*.sh" \) -path '*/tests/*' -executable | grep -q .; then
            categories+=("$(basename "$dir")")
        fi
    done < <(find "${PROJECT_ROOT}/ql" -mindepth 1 -maxdepth 1 -type d -print0)
    
    if [ ${#categories[@]} -eq 0 ]; then
        return 1
    fi
    
    printf "%s\n" "${categories[@]}" | sort
    debug "Found categories: ${categories[*]}"
}

discover_test_scripts_in_category() {
    local category="$1"
    debug "Discovering tests in category: $category"
    
    local scripts=()
    while IFS= read -r -d '' script; do
        scripts+=("$(basename "$script")")
    done < <(find "${PROJECT_ROOT}/ql/${category}" -type f \( -name "*_tests.sh" -o -name "test_*.sh" -o -name "run_*.sh" \) -path '*/tests/*' -executable -print0)
    
    if [ ${#scripts[@]} -eq 0 ]; then
        return 1
    fi
    
    printf "%s\n" "${scripts[@]}" | sort
    debug "Found scripts: ${scripts[*]}"
}

find_test_script_path() {
    local test_name="$1"
    local category="$2"
    debug "Finding path for test: $test_name (category: ${category:-all})"
    
    local script_path
    if [ -n "$category" ]; then
        script_path=$(find "${PROJECT_ROOT}/ql/${category}" -type f -name "$test_name" -path '*/tests/*' -executable -print -quit)
    else
        script_path=$(find "${PROJECT_ROOT}/ql" -type f -name "$test_name" -path '*/tests/*' -executable -print -quit)
    fi
    
    debug "Found script path: ${script_path:-none}"
    echo "$script_path"
}

select_test_interactively() {
    debug "Starting interactive test selection"
    
    # Get categories
    local categories_list
    categories_list=$(discover_test_categories) || {
        gum style --foreground 3 "No test categories found in ${PROJECT_ROOT}/ql/"
        exit 1
    }
    
    # Show categories header
    gum style \
        --border normal \
        --border-foreground 4 \
        --margin "1" \
        --padding "1" \
        --foreground 6 \
        "Available Test Categories"

    # Select category
    local selected_category
    selected_category=$(echo "$categories_list" | gum choose --header "Select a category to run tests from") || exit 0
    debug "Selected category: ${selected_category:-none}"
    
    if [ -z "$selected_category" ]; then
        gum style --foreground 3 "No category selected. Exiting."
        exit 0
    fi
    
    # Get tests in category
    local tests_list
    tests_list=$(discover_test_scripts_in_category "$selected_category") || {
        gum style --foreground 3 "No test scripts found in category '${selected_category}'"
        exit 1
    }
    
    # Show tests header
    gum style \
        --border normal \
        --border-foreground 4 \
        --margin "1" \
        --padding "1" \
        --foreground 6 \
        "Available Tests in ${selected_category}"

    # Select test
    local selected_script
    selected_script=$(echo "$tests_list" | gum choose --header "Select a test to run") || exit 0
    debug "Selected script: ${selected_script:-none}"
    
    if [ -z "$selected_script" ]; then
        gum style --foreground 3 "No test selected. Exiting."
        exit 0
    fi
    
    # Get full path
    local script_path
    script_path=$(find_test_script_path "$selected_script" "$selected_category")
    debug "Resolved path: ${script_path:-none}"
    
    if [ -z "$script_path" ]; then
        gum style --foreground 1 "Error: Could not find path for test '${selected_script}' in category '${selected_category}'"
        exit 1
    fi
    
    # Only print the script path, nothing else!
    echo "$script_path"
}

execute_and_parse_script() {
    local script_path="$1"
    local script_display_name
    script_display_name=$(realpath --relative-to="${PROJECT_ROOT}" "$script_path")

    # Create an eye-catching header for the test run
    gum style \
        --border double \
        --border-foreground magenta \
        --padding "1" \
        --margin "1" \
        --align center \
        --width 100 \
        "🧪 Test Execution Started 🧪" \
        "Script: ${script_display_name}" \
        "Path: ${script_path}"
    
    echo # Spacer

    # Reset counters for this script run
    script_total_items=0
    script_passed_items=0
    script_failed_items=0
    run_summary_buffer="" 
    reset_current_item_vars # Ensure clean state before parsing

    # Execute the script and process its output line by line
    # The script is expected to be executable and handle its own pathing relative to PROJECT_ROOT
    # Pipe stderr to stdout to ensure all output is captured by the while loop
    if ! "$script_path" 2>&1 | while IFS= read -r line; do
        if [[ "$line" == TEST_SCRIPT_NAME:* ]]; then
            current_test_script_name="${line#TEST_SCRIPT_NAME: }"
        elif [[ "$line" == TEST_ITEM_ID:* ]]; then
            if [[ -n "$current_test_item_id" ]]; then # Process previous item if ID was set
                display_test_item_result
                reset_current_item_vars
            fi
            current_test_item_id="${line#TEST_ITEM_ID: }"
        elif [[ "$line" == DESCRIPTION:* ]]; then
            current_description="${line#DESCRIPTION: }"
        elif [[ "$line" == OVERALL_STATUS:* ]]; then
            current_overall_status="${line#OVERALL_STATUS: }"
        elif [[ "$line" == FAIL_REASON:* ]]; then
            current_fail_reason="${line#FAIL_REASON: }"
        elif [[ "$line" == CPP_EXIT_CODE:* ]]; then
            current_cpp_exit_code="${line#CPP_EXIT_CODE: }"
        elif [[ "$line" == MOJO_EXIT_CODE:* ]]; then
            current_mojo_exit_code="${line#MOJO_EXIT_CODE: }"
        elif [[ "$line" == CPP_STDOUT_BEGIN ]]; then in_cpp_stdout=true; current_cpp_stdout=""; continue;
        elif [[ "$line" == CPP_STDOUT_END ]]; then in_cpp_stdout=false; continue;
        elif [[ "$in_cpp_stdout" == true ]]; then current_cpp_stdout+="$line\\n"; continue;
        elif [[ "$line" == CPP_STDERR_BEGIN ]]; then in_cpp_stderr=true; current_cpp_stderr=""; continue;
        elif [[ "$line" == CPP_STDERR_END ]]; then in_cpp_stderr=false; continue;
        elif [[ "$in_cpp_stderr" == true ]]; then current_cpp_stderr+="$line\\n"; continue;
        elif [[ "$line" == MOJO_STDOUT_BEGIN ]]; then in_mojo_stdout=true; current_mojo_stdout=""; continue;
        elif [[ "$line" == MOJO_STDOUT_END ]]; then in_mojo_stdout=false; continue;
        elif [[ "$in_mojo_stdout" == true ]]; then current_mojo_stdout+="$line\\n"; continue;
        elif [[ "$line" == MOJO_STDERR_BEGIN ]]; then in_mojo_stderr=true; current_mojo_stderr=""; continue;
        elif [[ "$line" == MOJO_STDERR_END ]]; then in_mojo_stderr=false; continue;
        elif [[ "$in_mojo_stderr" == true ]]; then current_mojo_stderr+="$line\\n"; continue;
        elif [[ "$line" == DIFF_OUTPUT_BEGIN ]]; then in_diff_output=true; current_diff_output=""; continue;
        elif [[ "$line" == DIFF_OUTPUT_END ]]; then in_diff_output=false; continue;
        elif [[ "$in_diff_output" == true ]]; then current_diff_output+="$line\\n"; continue;
        elif [[ "$line" == END_OF_TEST_ITEM ]]; then
            display_test_item_result
            reset_current_item_vars
        elif [[ "$line" == RUN_SCRIPT_SUMMARY_BEGIN ]]; then in_run_summary=true; run_summary_buffer=""; continue;
        elif [[ "$line" == RUN_SCRIPT_SUMMARY_END ]]; then in_run_summary=false; continue;
        elif [[ "$in_run_summary" == true ]]; then run_summary_buffer+="$line\\n"; continue;
        # Add a catch-all for lines not matching known patterns within active blocks to avoid losing script stderr
        elif [[ "$in_cpp_stdout" == true || "$in_cpp_stderr" == true || "$in_mojo_stdout" == true || "$in_mojo_stderr" == true || "$in_diff_output" == true || "$in_run_summary" == true ]]; then
            : # Already handled by appending to buffer
        else
            # Lines that are not part of any block and not a key might be script's own stderr/debug messages.
            # For now, these are ignored unless the script explicitly puts them in a defined block.
            # To capture them, one might echo them here, or log them separately.
            : 
        fi
    done; then
        # This specific 'then' block after 'while' is tricky with 'set -e'.
        # The exit status of the pipeline is the exit status of the last command.
        # If "$script_path" fails, 'set -e' should cause script to exit.
        # If 'while' fails, that's another scenario.
        true 
    fi
    script_pipeline_status=${PIPESTATUS[0]} # Get exit status of the test script itself

    # Process the last test item if it wasn't terminated by END_OF_TEST_ITEM
    if [[ -n "$current_test_item_id" ]]; then
        display_test_item_result
        reset_current_item_vars # Clean up after the final item
    fi

    # Display the run summary from the script's output if captured
    if [[ -n "$run_summary_buffer" ]]; then
        gum style \
            --border double \
            --border-foreground green \
            --padding "1" \
            --margin "1" \
            --align left \
            --width 100 \
            "📋 Detailed Output from ${script_display_name}:" \
            "$(echo -e "${run_summary_buffer}")"
    fi
    
    # Calculate percentages for the progress display
    local pass_percentage=0
    local fail_percentage=0
    if [ "$script_total_items" -gt 0 ]; then
        pass_percentage=$((script_passed_items * 100 / script_total_items))
        fail_percentage=$((script_failed_items * 100 / script_total_items))
    fi
    
    # Create a visually appealing final summary
    local summary_content
    summary_content="📊 Test Results Summary for ${script_display_name}"
    summary_content+=$'\n\n'"Total Tests: ${script_total_items}"
    summary_content+=$'\n'"✓ Passed: ${script_passed_items} (${pass_percentage}%)"
    summary_content+=$'\n'"✗ Failed: ${script_failed_items} (${fail_percentage}%)"
    
    if [ "$script_pipeline_status" -ne 0 ]; then
        summary_content+=$'\n\n'"⚠️  Script exited with status ${script_pipeline_status}"
    fi
    
    gum style \
        --border double \
        --border-foreground blue \
        --padding "1" \
        --margin "1" \
        --align center \
        --width 100 \
        "$summary_content"

    # Propagate failure if any items failed or script itself failed
    if [ "$script_failed_items" -gt 0 ] || [ "$script_pipeline_status" -ne 0 ]; then
        return 1
    fi
    return 0
}

main() {
    debug "Starting main function"
    local script_to_run=""
    
    if [ -n "$1" ]; then
        debug "Argument provided: $1"
        # Argument provided - try to find the test by name
        if [[ "$1" != /* ]] && [[ "$1" != ./* ]]; then
            debug "Treating as test name"
            script_to_run=$(find_test_script_path "$1")
            
            if [ -z "$script_to_run" ]; then
                gum style --foreground 1 "Error: Test script '$1' not found."
                gum style "Note: You can provide either:"
                gum style "  - Just the script name (e.g., 'run_europe_tests.sh')"
                gum style "  - A path relative to the project root"
                gum style "  - An absolute path"
                exit 1
            fi
        else
            debug "Treating as path"
            local potential_path_rel="${PROJECT_ROOT}/$1"
            local potential_path_direct="$1"
            
            if [ -f "$potential_path_rel" ] && [ -x "$potential_path_rel" ]; then
                script_to_run=$(realpath "$potential_path_rel")
            elif [ -f "$potential_path_direct" ] && [ -x "$potential_path_direct" ]; then
                script_to_run=$(realpath "$potential_path_direct")
            fi
            
            if [ -z "$script_to_run" ]; then
                gum style --foreground 1 "Error: Test script '$1' not found or not executable."
                gum style "Searched at: "
                gum style "  (relative to project) $potential_path_rel"
                gum style "  (as provided) $potential_path_direct"
                exit 1
            fi
        fi
        debug "Found script to run: $script_to_run"
    else
        debug "No argument provided, starting interactive selection"
        # Only capture the output of select_test_interactively (should be the path only)
        script_to_run=$(select_test_interactively)
        debug "Interactive selection returned: ${script_to_run:-none}"
    fi
    
    if [ -n "$script_to_run" ]; then
        debug "Executing script: $script_to_run"
        execute_and_parse_script "$script_to_run"
        exit $?
    else
        gum style --foreground 1 "Error: No test script was selected or determined for execution."
        exit 1
    fi
}

main "$@" 