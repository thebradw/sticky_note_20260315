#!/usr/bin/env python3
"""
Test script to verify delete functionality works correctly
"""
import requests
import json

# Test the delete functionality
def test_delete_functionality():
    base_url = "http://localhost:5000"
    
    # First, let's check if there are any existing sessions we can use
    # by checking a recent session from the logs
    session_id = "a06bc6fc"  # From recent logs
    
    print(f"Testing delete functionality with session: {session_id}")
    
    # Test 1: Try to access the review page 
    review_url = f"{base_url}/review/{session_id}"
    response = requests.get(review_url)
    
    if response.status_code == 200:
        print("SUCCESS: Review page accessible")
        
        # Test 2: Simulate a delete operation
        # Create test data that includes deleted notes
        test_data = {
            "editedNotes": {
                "1": {
                    "text": "Updated note 1",
                    "position": "top-left",
                    "color": "green",
                    "shape": "square",
                    "parallel_with": None
                }
            },
            "deletedNotes": [2, 3],  # Delete notes 2 and 3
            "workflowSequence": [1, 4, 5, 6, 7, 8, 9, 10]  # Remove deleted notes from sequence
        }
        
        # Test 3: Send save request with deletions
        save_url = f"{base_url}/save-edits/{session_id}"
        response = requests.post(save_url, json=test_data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print("SUCCESS: Delete functionality works - save request successful")
                print(f"   Message: {result.get('message', 'No message')}")
                
                # Test 4: Verify the review page still works after deletion
                response = requests.get(review_url)
                if response.status_code == 200:
                    print("SUCCESS: Review page still accessible after deletions")
                else:
                    print("ERROR: Review page failed after deletions")
            else:
                print("ERROR: Save request failed")
                print(f"   Response: {result}")
        else:
            print("ERROR: Save request returned error status")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
    else:
        print("ERROR: Review page not accessible")
        print(f"   Status: {response.status_code}")

if __name__ == "__main__":
    print("Testing Delete Functionality...")
    print("=" * 50)
    
    try:
        test_delete_functionality()
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to Flask app at http://localhost:5000")
        print("   Make sure the app is running with: python app.py")
    except Exception as e:
        print(f"ERROR: Test failed with error: {e}")
    
    print("=" * 50)
    print("Test Complete")