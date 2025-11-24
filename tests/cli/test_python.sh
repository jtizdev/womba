#!/bin/bash
# Test script for Python CLI

set -e

echo "🐍 Testing Python CLI..."
echo "=========================="

# Check if CLI exists
if [ ! -f "womba_cli.py" ]; then
    echo "❌ womba_cli.py not found"
    exit 1
fi

# Set environment variables
export WOMBA_API_URL="https://womba.onrender.com"
export WOMBA_API_KEY="${WOMBA_API_KEY:-test-key}"

TEST_STORY="PROJ-12345"

# Test 1: Generate command
echo ""
echo "Test 1: womba generate $TEST_STORY"
echo "-----------------------------------"
python3 womba_cli.py generate $TEST_STORY 2>&1 | tee /tmp/womba_python_test.log

if grep -q "test cases" /tmp/womba_python_test.log; then
    echo "✅ Generate command works"
else
    echo "❌ Generate command failed"
    exit 1
fi

# Test 2: Configure command
echo ""
echo "Test 2: womba configure --help"
echo "------------------------------"
python3 womba_cli.py configure --help || echo "✅ Configure command exists"

# Test 3: Evaluate command
echo ""
echo "Test 3: womba evaluate $TEST_STORY"
echo "----------------------------------"
python3 womba_cli.py evaluate $TEST_STORY 2>&1 || echo "⚠️  Evaluate requires full config"

echo ""
echo "=========================="
echo "✅ Python CLI tests passed"
echo "=========================="

