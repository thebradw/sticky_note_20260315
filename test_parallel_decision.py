#!/usr/bin/env python3
"""
Test script to verify parallel step and decision branch detection
"""
import os
import sys

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_analyzer import StickyNoteAnalyzer

def test_analyze_workflow():
    """Test the updated analyze_workflow with parallel and decision detection"""
    
    print("Testing Updated Sticky Note Analyzer")
    print("=" * 60)
    
    # Initialize analyzer
    analyzer = StickyNoteAnalyzer()
    
    # Test image path - USE THE CORRECT TEST CASE IMAGE
    test_image = "test_images/newspaper_1header_decision.jpeg"
    
    if not os.path.exists(test_image):
        print(f"ERROR: Test image not found: {test_image}")
        print("Looking for available test images...")
        test_dir = "test_images"
        if os.path.exists(test_dir):
            images = [f for f in os.listdir(test_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
            if images:
                print(f"Available test images:")
                for i, img in enumerate(images, 1):
                    print(f"  {i}. {img}")
                # Use first image as fallback
                test_image = os.path.join(test_dir, images[0])
                print(f"\nUsing: {test_image}")
            else:
                print("No images found in test_images directory")
                return False
        else:
            print("test_images directory not found")
            return False
    
    print(f"\nAnalyzing: {test_image}")
    print("-" * 60)
    
    # Run analysis
    result = analyzer.analyze_workflow(test_image)
    
    if not result:
        print("ERROR: Analysis failed")
        return False
    
    print("\n✅ Analysis completed successfully!")
    print("-" * 60)
    
    # Check for new features
    sticky_notes = result.get('sticky_notes', [])
    print(f"\nTotal notes detected: {len(sticky_notes)}")
    
    # Check for parallel relationships
    parallel_notes = [n for n in sticky_notes if n.get('parallel_with')]
    if parallel_notes:
        print(f"\n✅ PARALLEL STEPS DETECTED: {len(parallel_notes)} notes")
        for note in parallel_notes:
            parallel_note = next((n for n in sticky_notes if n['id'] == note['parallel_with']), None)
            parallel_text = parallel_note['text'][:30] if parallel_note else "Unknown"
            print(f"   Note {note['id']} ({note['text'][:30]}) parallel with Note {note['parallel_with']} ({parallel_text})")
    else:
        print("\n⚠️  No parallel relationships detected")
    
    # Check for decision branches
    decision_notes = [n for n in sticky_notes if n.get('decision_branches')]
    if decision_notes:
        print(f"\n✅ DECISION DIAMONDS DETECTED: {len(decision_notes)} diamonds")
        for note in decision_notes:
            branches = note.get('decision_branches', {})
            print(f"   Note {note['id']} ({note['text'][:30]})")
            print(f"      Yes → Step {branches.get('yes_next_step')}")
            print(f"      No  → Step {branches.get('no_next_step')}")
            print(f"      Rejoin at Step {branches.get('rejoin_step')}")
    else:
        print("\n⚠️  No decision diamonds detected")
    
    # Print all notes to understand the workflow
    print("\n" + "=" * 60)
    print("ALL NOTES:")
    print("=" * 60)
    for note in sticky_notes:
        parallel_info = f" || PARALLEL WITH {note['parallel_with']}" if note.get('parallel_with') else ""
        decision_info = " || DECISION DIAMOND" if note.get('decision_branches') else ""
        print(f"{note['id']:2d}. [{note.get('shape', 'square'):10s}] {note.get('text', 'N/A')[:40]:40s}{parallel_info}{decision_info}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    try:
        success = test_analyze_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
