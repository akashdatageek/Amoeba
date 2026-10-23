#!/bin/bash
# Acceptance scenarios for wordfreq.py

run_test() {
    local desc=$1
    local args=$2
    local input_content=$3
    local filename="test_input.txt"
    
    if [ -n "$input_content" ]; then
        echo -n "$input_content" > "$filename"
    elif [ "$input_content" == "MISSING" ]; then
        rm -f "$filename"
    else
        # Empty file
        echo -n "" > "$filename"
    fi

    echo "Scenario: $desc"
    echo "Args: $args"
    
    # Run the tool and capture output
    # We use a subshell to capture stderr and stdout separately
    # and then use cat -A to show tabs
    set +e
    stdout=$(python3 wordfreq.py $args 2>stderr.txt)
    exit_code=$?
    stderr=$(cat stderr.txt)
    set -e

    echo "Exit Code: $exit_code"
    echo "Stdout (cat -A):"
    echo "$stdout" | cat -A
    echo "Stderr:"
    echo "$stderr"
    echo "--------------------------------------------------"
}

# Setup
touch wordfreq.py # Ensure it exists if not already

# Scenario 1: -n 2
run_test "-n 2" "test_input.txt -n 2" "The the THE café cafe 'tis dogs' rock'n'roll"

# Scenario 2: --min-length 4
run_test "--min-length 4" "test_input.txt --min-length 4" "The the THE café cafe 'tis dogs' rock'n'roll"

# Scenario 3: Default n with > 10 words
run_test "Default n > 10" "test_input.txt" "a b c d e f g h i j k l"

# Scenario 4: Ties
run_test "Ties" "test_input.txt" "b b a a"

# Scenario 5: Missing path
run_test "Missing path" "nonexistent.txt" "MISSING"

# Scenario 6: -n 0
run_test "-n 0" "test_input.txt -n 0" "some text"

# Scenario 7: -n -3
run_test "-n -3" "test_input.txt -n -3" "some text"

# Scenario 8: Empty file
run_test "Empty file" "test_input.txt" ""

rm -f test_input.txt stderr.txt
