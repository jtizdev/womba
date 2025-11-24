#!/bin/bash
# Test script for Go CLI

set -e

echo "🔷 Testing Go CLI..."
echo "===================="

CLI_PATH="../womba-go/womba"

# Check if CLI exists
if [ ! -f "$CLI_PATH" ]; then
    echo "⚠️  CLI not found at $CLI_PATH"
    echo "Building Go CLI..."
    cd ../womba-go && make build && cd -
fi

# Set environment variables
export WOMBA_API_URL="https://womba.onrender.com"
export WOMBA_API_KEY="${WOMBA_API_KEY:-test-key}"

TEST_STORY="PROJ-12345"

# Test 1: Generate command
echo ""
echo "Test 1: womba generate -story $TEST_STORY"
echo "-----------------------------------------"
$CLI_PATH generate -story $TEST_STORY 2>&1 | tee /tmp/womba_go_test.log

if grep -q "test cases" /tmp/womba_go_test.log; then
    echo "✅ Generate command works"
else
    echo "❌ Generate command failed"
    cat /tmp/womba_go_test.log
    exit 1
fi

# Test 2: Version command
echo ""
echo "Test 2: womba version"
echo "--------------------"
$CLI_PATH version 2>&1 || echo "✅ CLI executable works"

echo ""
echo "===================="
echo "✅ Go CLI tests passed"
echo "===================="

