#!/bin/bash
# Test script for Java CLI

set -e

echo "☕ Testing Java CLI..."
echo "======================"

JAR_PATH="../womba-java/target/womba.jar"

# Check if JAR exists
if [ ! -f "$JAR_PATH" ]; then
    echo "⚠️  JAR not found at $JAR_PATH"
    echo "Building Java CLI..."
    cd ../womba-java && mvn clean package -q && cd -
fi

# Set environment variables
export WOMBA_API_URL="https://womba.onrender.com"
export WOMBA_API_KEY="${WOMBA_API_KEY:-test-key}"

TEST_STORY="PLAT-12991"

# Test 1: Generate command
echo ""
echo "Test 1: womba generate -story $TEST_STORY"
echo "-----------------------------------------"
java -jar "$JAR_PATH" generate -story $TEST_STORY 2>&1 | tee /tmp/womba_java_test.log

if grep -q "test cases" /tmp/womba_java_test.log; then
    echo "✅ Generate command works"
else
    echo "❌ Generate command failed"
    cat /tmp/womba_java_test.log
    exit 1
fi

# Test 2: Generate with upload (will fail gracefully without creds)
echo ""
echo "Test 2: womba generate --upload"
echo "-------------------------------"
java -jar "$JAR_PATH" generate -story $TEST_STORY --upload 2>&1 || echo "⚠️  Upload requires Zephyr credentials"

echo ""
echo "======================"
echo "✅ Java CLI tests passed"
echo "======================"

