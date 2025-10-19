#!/bin/bash
# Master test script - Run all CLI tests

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Womba CLI Test Suite - Testing All CLIs               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Change to tests/cli directory
cd "$(dirname "$0")"

PASSED=0
FAILED=0
SKIPPED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_script="$2"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Running: $test_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if ./$test_script; then
        echo "✅ $test_name PASSED"
        ((PASSED++))
    else
        exit_code=$?
        if [ $exit_code -eq 77 ]; then
            echo "⏭️  $test_name SKIPPED"
            ((SKIPPED++))
        else
            echo "❌ $test_name FAILED"
            ((FAILED++))
        fi
    fi
}

# Run all CLI tests
run_test "Python CLI" "test_python.sh"
run_test "Java CLI" "test_java.sh"
run_test "Go CLI" "test_go.sh"
run_test "Node.js CLI" "test_node.sh"

# Summary
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                       Test Summary                             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ Passed:  $PASSED"
echo "❌ Failed:  $FAILED"
echo "⏭️  Skipped: $SKIPPED"
echo ""

if [ $FAILED -gt 0 ]; then
    echo "❌ Some tests failed!"
    exit 1
else
    echo "✅ All tests passed!"
    exit 0
fi

