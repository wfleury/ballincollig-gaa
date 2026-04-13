"""
Test script to sync just one result to ClubZap for testing
"""
import json
import os

# Read the full results file
with open('new_results_to_sync.json', 'r') as f:
    data = json.load(f)

# Take just the first result for testing
test_result = data['results'][0]
test_data = {
    'timestamp': data['timestamp'],
    'count': 1,
    'results': [test_result]
}

# Save as test file
with open('test_single_result.json', 'w') as f:
    json.dump(test_data, f, indent=2)

print("Created test_single_result.json with:")
print(f"  {test_result['date']} - {test_result['team']} {test_result['our_score']} v {test_result['opponent_score']} {test_result['opponent']} ({test_result['result']})")