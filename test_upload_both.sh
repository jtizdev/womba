#!/bin/bash
# Test script to upload both test cases (manual and generated) to Zephyr

echo "=== Testing Zephyr Upload with Both Test Cases ==="
echo ""

# Test payload with both test cases
curl -X POST "http://localhost:8000/api/v1/zephyr/upload" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_key": "PLAT-13541",
    "project_key": "PLAT",
    "test_cases": [
      {
        "id": "TC-MANUAL-1763467788189",
        "title": "New Manual Test Case"
      },
      {
        "id": "TC-PLAT-13541-1",
        "title": "Policies tab opens to show correct policy list for application"
      }
    ]
  }' | python3 -m json.tool

echo ""
echo "=== Check logs for upload details ==="

