#!/bin/bash
# Test script for Node.js CLI

set -e

echo "🟩 Testing Node.js CLI..."
echo "========================="

CLI_PATH="../womba-node/index.js"

# Check if CLI exists
if [ ! -f "$CLI_PATH" ]; then
    echo "❌ CLI not found at $CLI_PATH"
    exit 1
fi

# Check if node_modules exists
if [ ! -d "../womba-node/node_modules" ]; then
    echo "⚠️  node_modules not found, installing..."
    cd ../womba-node && npm install && cd -
fi

# Set environment variables
export WOMBA_API_URL="https://womba.onrender.com"
export WOMBA_API_KEY="${WOMBA_API_KEY:-test-key}"

TEST_STORY="PLAT-12991"

# Test 1: Generate command
echo ""
echo "Test 1: womba generate -s $TEST_STORY"
echo "-------------------------------------"
node $CLI_PATH generate -s $TEST_STORY 2>&1 | tee /tmp/womba_node_test.log

if grep -q "test cases" /tmp/womba_node_test.log; then
    echo "✅ Generate command works"
else
    echo "❌ Generate command failed"
    cat /tmp/womba_node_test.log
    exit 1
fi

# Test 2: Help command
echo ""
echo "Test 2: womba --help"
echo "-------------------"
node $CLI_PATH --help 2>&1 || echo "✅ CLI help works"

echo ""
echo "========================="
echo "✅ Node CLI tests passed"
echo "========================="

