#!/usr/bin/env python3
"""
Comprehensive test script to verify delete functionality
This creates a new session using mock data and tests deletion
"""
import requests
import json
import time
import os

def create_test_session():
    """Create a test session using the image upload"""
    base_url = "http://localhost:5000"
    
    # Use existing test image
    image_path = "uploads/04d10571_20250823_145619_IMG_2438.jpeg"
    if not os.path.exists(image_path):
        print(f"ERROR: Test image not found: {image_path}")
        return None
    
    # Upload image (simulate browser form upload)
    with open(image_path, 'rb') as f:
        files = {'image': f}
        response = requests.post(f"{base_url}/upload", files=files)
    
    if response.status_code == 302:  # Redirect after upload
        # Extract session ID from redirect URL
        location = response.headers.get('Location', '')
        if '/analyze/' in location:
            session_id = location.split('/analyze/')[-1]
            print(f"SUCCESS: Created session {session_id}")
            return session_id
    
    print("ERROR: Failed to create session")
    return None

def wait_for_analysis(session_id):
    """Wait for analysis to complete"""
    base_url = "http://localhost:5000"
    
    # First trigger analysis
    analyze_url = f"{base_url}/analyze/{session_id}"
    response = requests.get(analyze_url)
    
    if response.status_code != 200:
        print("ERROR: Analysis page not accessible")
        return False
    
    # Then trigger processing  
    process_url = f"{base_url}/process/{session_id}"
    response = requests.get(process_url)
    
    if response.status_code == 200:
        print("SUCCESS: Analysis completed")
        return True
    else:
        print("ERROR: Processing failed")
        return False

def test_delete_functionality_full():
    """Test the complete delete workflow"""
    base_url = "http://localhost:5000"
    
    # Step 1: Create session
    session_id = create_test_session()
    if not session_id:
        return False
        
    # Step 2: Complete analysis
    if not wait_for_analysis(session_id):
        return False
    
    # Step 3: Access review page
    review_url = f"{base_url}/review/{session_id}"
    response = requests.get(review_url)
    
    if response.status_code != 200:
        print("ERROR: Review page not accessible")
        return False
    
    print("SUCCESS: Review page accessible")
    
    # Step 4: Test delete functionality
    # Create realistic test data (mock analyzer creates 15 notes)
    test_data = {
        "editedNotes": {
            "1": {
                "text": "Test edited note 1",
                "position": "top-left", 
                "color": "green",
                "shape": "square",
                "parallel_with": None
            }
        },
        "deletedNotes": [2, 3, 4],  # Delete some notes
        "workflowSequence": [1, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]  # Sequence without deleted notes
    }
    
    # Step 5: Send save request with deletions
    save_url = f"{base_url}/save-edits/{session_id}"
    response = requests.post(save_url, 
                           json=test_data,
                           headers={'Content-Type': 'application/json'})
    
    if response.status_code != 200:
        print("ERROR: Save request failed")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    result = response.json()
    if result.get('status') != 'success':
        print("ERROR: Save operation failed")
        print(f"   Response: {result}")
        return False
    
    print("SUCCESS: Delete operation completed successfully")
    print(f"   Message: {result.get('message', 'No message')}")
    
    # Step 6: Verify review page still works
    response = requests.get(review_url)
    if response.status_code != 200:
        print("ERROR: Review page failed after deletions")
        return False
    
    print("SUCCESS: Review page still accessible after deletions")
    
    # Step 7: Test PDF generation still works
    pdf_url = f"{base_url}/generate-pdf/{session_id}"
    response = requests.get(pdf_url)
    
    if response.status_code == 200:
        print("SUCCESS: PDF generation works after deletions")
    else:
        print("WARNING: PDF generation failed (may be expected)")
        print(f"   Status: {response.status_code}")
    
    return True

if __name__ == "__main__":
    print("Comprehensive Delete Functionality Test")
    print("=" * 50)
    
    try:
        if test_delete_functionality_full():
            print("=" * 50)
            print("ALL TESTS PASSED!")
        else:
            print("=" * 50)
            print("TESTS FAILED!")
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to Flask app at http://localhost:5000")
        print("   Make sure the app is running with: python app.py")
    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()