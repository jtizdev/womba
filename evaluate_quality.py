"""
Evaluate test quality using the quality scorer.
"""

import asyncio
import json
import sys
from pathlib import Path

from src.ai.quality_scorer import TestQualityScorer
from src.models.test_case import TestCase, TestStep
from src.models.story import JiraStory


async def evaluate_test_plan(story_key: str):
    """Evaluate test plan quality."""
    
    # Load test plan
    test_plan_file = Path(f"test_plan_{story_key}_enhanced.json")
    if not test_plan_file.exists():
        print(f"❌ Test plan file not found: {test_plan_file}")
        return
    
    with open(test_plan_file) as f:
        data = json.load(f)
    
    # Convert to models
    story = JiraStory(
        key=data['story']['key'],
        summary=data['story']['summary'],
        description=data['story']['description'],
        issue_type='Story',
        status=data['story']['status'],
        priority=data['story']['priority'],
        reporter='system',
        labels=[],
        components=[],
        created='2024-01-01T00:00:00.000+0000',
        updated='2024-01-01T00:00:00.000+0000'
    )
    
    test_cases = []
    for tc_data in data['test_cases']:
        steps = [
            TestStep(
                step_number=step['step_number'],
                action=step['action'],
                expected_result=step['expected_result'],
                test_data=step.get('test_data')
            )
            for step in tc_data['steps']
        ]
        
        test_case = TestCase(
            title=tc_data['title'],
            description=tc_data['description'],
            preconditions=tc_data['preconditions'],
            steps=steps,
            expected_result=tc_data['expected_result'],
            priority=tc_data['priority'],
            test_type=tc_data['test_type'],
            tags=tc_data['tags'],
            automation_candidate=tc_data['automation_candidate'],
            risk_level=tc_data['risk_level'],
            related_existing_tests=tc_data.get('related_existing_tests', [])
        )
        test_cases.append(test_case)
    
    # Score tests
    scorer = TestQualityScorer()
    results = scorer.score_test_plan(test_cases, story)
    
    # Display results
    print("\n" + "="*80)
    print(f"📊 QUALITY EVALUATION FOR {story_key}")
    print("="*80)
    print(f"\nStory: {story.summary}")
    print(f"\nGenerated: {len(test_cases)} test cases")
    print("\n" + "-"*80)
    print("OVERALL SCORES")
    print("-"*80)
    print(f"Average Score:    {results['average_score']:.1f}/100")
    print(f"Min Score:        {results['min_score']:.1f}/100")
    print(f"Max Score:        {results['max_score']:.1f}/100")
    print(f"Passing Tests:    {results['passing_tests']}/{results['total_tests']} ({results['pass_rate']*100:.0f}%)")
    print(f"Target Pass Rate: 70%")
    print(f"\n{'✅ PASS' if results['pass_rate'] >= 0.7 else '❌ FAIL'} - {'Meets' if results['pass_rate'] >= 0.7 else 'Below'} 70% quality target")
    
    # Individual test scores
    print("\n" + "-"*80)
    print("INDIVIDUAL TEST SCORES")
    print("-"*80)
    
    for i, (tc, score) in enumerate(zip(test_cases, results['individual_scores'])):
        status = "✅" if score >= 60 else "❌"
        print(f"\n{i+1}. {tc.title}")
        print(f"   Score: {score:.1f}/100 {status}")
        print(f"   Steps: {len(tc.steps)} | Priority: {tc.priority} | Type: {tc.test_type}")
        
        # Breakdown
        feature_score = scorer._score_feature_specificity(tc, story)
        steps_score = scorer._score_step_completeness(tc)
        indicator_score = scorer._score_specific_indicators(tc)
        data_score = scorer._score_test_data(tc)
        
        print(f"   Breakdown:")
        print(f"     • Feature Specificity: {feature_score:.0f}/30")
        print(f"     • Step Completeness:   {steps_score:.0f}/20")
        print(f"     • Specific Indicators: {indicator_score:.0f}/25")
        print(f"     • Test Data Quality:   {data_score:.0f}/25")
    
    # Recommendations
    print("\n" + "-"*80)
    print("RECOMMENDATIONS")
    print("-"*80)
    
    low_score_tests = [
        (i+1, tc.title, score) 
        for i, (tc, score) in enumerate(zip(test_cases, results['individual_scores']))
        if score < 60
    ]
    
    if low_score_tests:
        print("\n⚠️ Low-quality tests that should be improved:")
        for idx, title, score in low_score_tests:
            print(f"  {idx}. {title} ({score:.1f}/100)")
        print("\nSuggestions:")
        print("  • Add more specific feature terminology")
        print("  • Increase steps to 3-5 per test")
        print("  • Include specific API endpoints or UI elements")
        print("  • Add realistic test data examples")
    else:
        print("\n✅ All tests meet minimum quality threshold (60/100)")
    
    # Strengths
    print("\n" + "-"*80)
    print("STRENGTHS")
    print("-"*80)
    
    high_score_tests = [
        (i+1, tc.title, score) 
        for i, (tc, score) in enumerate(zip(test_cases, results['individual_scores']))
        if score >= 75
    ]
    
    if high_score_tests:
        print("\n🌟 High-quality tests:")
        for idx, title, score in high_score_tests:
            print(f"  {idx}. {title} ({score:.1f}/100)")
    
    # Feature coverage
    feature_keywords = ['asset', 'type', 'source', 'virtual', 'external', 'internal', 'change']
    covered_keywords = set()
    for tc in test_cases:
        test_text = f"{tc.title} {tc.description}".lower()
        for kw in feature_keywords:
            if kw in test_text:
                covered_keywords.add(kw)
    
    print(f"\n📋 Feature Coverage:")
    print(f"  Covered {len(covered_keywords)}/{len(feature_keywords)} key concepts")
    print(f"  Keywords: {', '.join(sorted(covered_keywords))}")
    
    # Final verdict
    print("\n" + "="*80)
    if results['pass_rate'] >= 0.7:
        print("✅ FINAL VERDICT: TEST PLAN READY FOR UPLOAD")
    else:
        print("⚠️ FINAL VERDICT: TEST PLAN NEEDS IMPROVEMENT")
    print("="*80 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 evaluate_quality.py <story_key>")
        sys.exit(1)
    
    story_key = sys.argv[1]
    asyncio.run(evaluate_test_plan(story_key))

