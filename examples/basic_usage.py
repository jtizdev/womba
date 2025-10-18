"""
Example usage of Womba API.

This script demonstrates how to use the Womba API to generate
test plans from Jira stories.
"""

import asyncio
import json

import httpx


async def main():
    """Main example function."""
    base_url = "http://localhost:8000"

    async with httpx.AsyncClient() as client:
        # Example 1: Fetch a Jira story
        print("=" * 60)
        print("Example 1: Fetching Jira Story")
        print("=" * 60)

        issue_key = "PROJ-123"  # Replace with your actual issue key
        response = await client.get(f"{base_url}/api/v1/stories/{issue_key}")

        if response.status_code == 200:
            story = response.json()
            print(f"✓ Successfully fetched story: {story['key']}")
            print(f"  Summary: {story['summary']}")
            print(f"  Status: {story['status']}")
            print(f"  Priority: {story['priority']}")
        else:
            print(f"✗ Error fetching story: {response.status_code}")
            print(response.text)
            return

        # Example 2: Get comprehensive story context
        print("\n" + "=" * 60)
        print("Example 2: Fetching Story Context (with linked issues)")
        print("=" * 60)

        response = await client.get(f"{base_url}/api/v1/stories/{issue_key}/context")

        if response.status_code == 200:
            context = response.json()
            print(f"✓ Successfully fetched context")
            print(f"  Main story: {context['main_story']['key']}")
            print(f"  Linked stories: {len(context['linked_stories'])}")
            print(f"  Related bugs: {len(context['related_bugs'])}")
        else:
            print(f"✗ Error fetching context: {response.status_code}")

        # Example 3: Generate test plan (without Zephyr upload)
        print("\n" + "=" * 60)
        print("Example 3: Generating Test Plan")
        print("=" * 60)

        request_payload = {"issue_key": issue_key, "upload_to_zephyr": False}

        print("Generating test plan (this may take 10-30 seconds)...")
        response = await client.post(
            f"{base_url}/api/v1/test-plans/generate",
            json=request_payload,
            timeout=60.0,  # Increase timeout for AI generation
        )

        if response.status_code == 200:
            result = response.json()
            test_plan = result["test_plan"]

            print(f"✓ Successfully generated test plan!")
            print(f"\n📊 Test Plan Summary:")
            print(f"  {test_plan['summary']}")
            print(f"\n📈 Metadata:")
            print(f"  Total test cases: {test_plan['metadata']['total_test_cases']}")
            print(f"  Edge case tests: {test_plan['metadata']['edge_case_count']}")
            print(
                f"  Integration tests: {test_plan['metadata']['integration_test_count']}"
            )
            print(f"  AI Model: {test_plan['metadata']['ai_model']}")

            print(f"\n🧪 Test Cases:")
            for idx, test_case in enumerate(test_plan["test_cases"], 1):
                print(f"\n  {idx}. {test_case['title']}")
                print(f"     Priority: {test_case['priority']}")
                print(f"     Type: {test_case['test_type']}")
                print(f"     Steps: {len(test_case['steps'])}")
                print(f"     Automation: {'Yes' if test_case['automation_candidate'] else 'No'}")

            # Save test plan to file
            filename = f"test_plan_{issue_key}.json"
            with open(filename, "w") as f:
                json.dump(result, f, indent=2, default=str)
            print(f"\n💾 Test plan saved to: {filename}")

        else:
            print(f"✗ Error generating test plan: {response.status_code}")
            print(response.text)
            return

        # Example 4: Generate test plan WITH Zephyr upload
        print("\n" + "=" * 60)
        print("Example 4: Generating Test Plan with Zephyr Upload")
        print("=" * 60)

        proceed = input("Do you want to upload to Zephyr? (y/n): ")
        if proceed.lower() == "y":
            project_key = input("Enter your Jira project key (e.g., PROJ): ")

            request_payload = {
                "issue_key": issue_key,
                "upload_to_zephyr": True,
                "project_key": project_key,
            }

            print("Generating and uploading test plan...")
            response = await client.post(
                f"{base_url}/api/v1/test-plans/generate",
                json=request_payload,
                timeout=120.0,  # Longer timeout for Zephyr upload
            )

            if response.status_code == 200:
                result = response.json()
                zephyr_results = result.get("zephyr_results", {})

                print(f"✓ Successfully uploaded to Zephyr!")
                print(f"\n📤 Zephyr Upload Results:")
                for title, zephyr_key in zephyr_results.items():
                    if zephyr_key.startswith("ERROR"):
                        print(f"  ✗ {title}: {zephyr_key}")
                    else:
                        print(f"  ✓ {title}: {zephyr_key}")
            else:
                print(f"✗ Error: {response.status_code}")
                print(response.text)
        else:
            print("Skipping Zephyr upload.")

        print("\n" + "=" * 60)
        print("Examples completed!")
        print("=" * 60)


if __name__ == "__main__":
    print("\n🚀 Womba API Examples\n")
    print("Make sure the Womba API server is running on http://localhost:8000")
    print("Start it with: uvicorn src.api.main:app --reload\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user.")
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")

