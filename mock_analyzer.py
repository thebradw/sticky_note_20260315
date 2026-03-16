# mock_analyzer.py - Mock version for testing PDF generation
import os
import time

class StickyNoteAnalyzer:
    def __init__(self):
        print("Using mock analyzer for testing...")
    
    def analyze_workflow(self, image_path):
        """Mock analysis that returns sample data"""
        
        print(f"Mock analyzing: {os.path.basename(image_path)}")
        
        # Simulate processing time
        time.sleep(1)
        
        # Return mock analysis data
        mock_data = {
            "summary": "Mock workflow showing a 3-step process from planning to execution",
            "sticky_notes": [
                {
                    "id": 1,
                    "text": "Plan the project",
                    "color": "yellow",
                    "position": "top-left",
                    "shape": "rectangle"
                },
                {
                    "id": 2,
                    "text": "Design the solution",
                    "color": "blue",
                    "position": "top-center", 
                    "shape": "rectangle"
                },
                {
                    "id": 3,
                    "text": "Implement and test",
                    "color": "green",
                    "position": "top-right",
                    "shape": "rectangle"
                },
                {
                    "id": 4,
                    "text": "Review results",
                    "color": "pink",
                    "position": "bottom-center",
                    "shape": "oval"
                }
            ],
            "workflow_sequence": [1, 2, 3, 4]
        }
        
        print("Mock analysis complete!")
        return mock_data
    
    def find_duplicate_notes(self, all_results):
        """Mock duplicate finder"""
        return []  # No duplicates in mock data