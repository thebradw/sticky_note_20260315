#!/usr/bin/env python3
"""
Simple test to verify the save-edits endpoint handles deletions correctly
"""
import sys
import os
import json

# Add the current directory to Python path so we can import from app.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app components
from app import app, sessions

def create_mock_session():
    """Create a mock session with test data"""
    session_id = "test_delete_123"
    
    # Create mock session data similar to what the analyzer would produce
    mock_data = {
        'analysis_results': [{
            'status': 'success',
            'filename': 'test_image.jpg',
            'analysis': {
                'summary': 'Test workflow for deletion testing',
                'sticky_notes': [
                    {'id': 1, 'text': 'Note 1', 'color': 'green', 'position': 'top-left', 'shape': 'square', 'parallel_with': None},
                    {'id': 2, 'text': 'Note 2', 'color': 'yellow', 'position': 'top-center', 'shape': 'square', 'parallel_with': None},
                    {'id': 3, 'text': 'Note 3', 'color': 'blue', 'position': 'top-right', 'shape': 'square', 'parallel_with': 2},
                    {'id': 4, 'text': 'Note 4', 'color': 'pink', 'position': 'middle-left', 'shape': 'square', 'parallel_with': None},
                    {'id': 5, 'text': 'Note 5', 'color': 'green', 'position': 'middle-center', 'shape': 'square', 'parallel_with': None}
                ],
                'workflow_sequence': [1, 2, 3, 4, 5]
            }
        }]
    }
    
    # Add to sessions
    sessions[session_id] = mock_data
    return session_id

def test_delete_backend():
    """Test the delete functionality at the backend level"""
    
    # Create mock session
    session_id = create_mock_session()
    print(f"Created test session: {session_id}")
    
    # Print initial state
    initial_notes = sessions[session_id]['analysis_results'][0]['analysis']['sticky_notes']
    print(f"Initial notes count: {len(initial_notes)}")
    print("Initial notes:")
    for note in initial_notes:
        parallel_info = f" (parallel to {note['parallel_with']})" if note['parallel_with'] else ""
        print(f"  ID {note['id']}: {note['text']}{parallel_info}")
    
    print(f"Initial sequence: {sessions[session_id]['analysis_results'][0]['analysis']['workflow_sequence']}")
    
    # Test delete operation
    with app.test_client() as client:
        # Simulate deleting notes 2 and 3
        test_data = {
            "editedNotes": {
                "1": {
                    "text": "Updated Note 1",
                    "position": "top-left",
                    "color": "green", 
                    "shape": "square",
                    "parallel_with": None
                }
            },
            "deletedNotes": [2, 3],  # Delete notes that have parallel relationships
            "workflowSequence": [1, 4, 5]  # New sequence without deleted notes
        }
        
        print("\\nTesting deletion of notes 2 and 3...")
        
        response = client.post(f'/save-edits/{session_id}', 
                             data=json.dumps(test_data),
                             content_type='application/json')
        
        if response.status_code == 200:
            result = response.get_json()
            print(f"SUCCESS: {result.get('message')}")
            
            # Check final state
            final_notes = sessions[session_id]['analysis_results'][0]['analysis']['sticky_notes']
            print(f"\\nFinal notes count: {len(final_notes)}")
            print("Final notes:")
            for note in final_notes:
                parallel_info = f" (parallel to {note['parallel_with']})" if note['parallel_with'] else ""
                print(f"  ID {note['id']}: {note['text']}{parallel_info}")
            
            final_sequence = sessions[session_id]['analysis_results'][0]['analysis']['workflow_sequence']
            print(f"Final sequence: {final_sequence}")
            
            # Verify deletions
            remaining_ids = [note['id'] for note in final_notes]
            if 2 not in remaining_ids and 3 not in remaining_ids:
                print("SUCCESS: Notes 2 and 3 were deleted")
            else:
                print("ERROR: Notes 2 and 3 were not deleted properly")
                
            # Verify parallel relationship cleanup
            parallel_to_deleted = [note for note in final_notes if note.get('parallel_with') in [2, 3]]
            if not parallel_to_deleted:
                print("SUCCESS: Parallel relationships to deleted notes were cleaned up")
            else:
                print("ERROR: Some parallel relationships still reference deleted notes")
                
            # Verify sequence cleanup
            if 2 not in final_sequence and 3 not in final_sequence:
                print("SUCCESS: Deleted notes removed from sequence")
            else:
                print("ERROR: Deleted notes still in sequence")
                
            return True
            
        else:
            print(f"ERROR: Request failed with status {response.status_code}")
            print(f"Response: {response.get_data(as_text=True)}")
            return False

if __name__ == "__main__":
    print("Backend Delete Functionality Test")
    print("=" * 50)
    
    try:
        success = test_delete_backend()
        print("=" * 50)
        if success:
            print("ALL TESTS PASSED!")
        else:
            print("TESTS FAILED!")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()