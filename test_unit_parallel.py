#!/usr/bin/env python3
"""Unit test for parallel detection and pain point handling"""

# Mock notes with coordinates
mock_notes = [
    {
        'id': 1,
        'text': 'Step 1',
        'color': 'green',
        'shape': 'square',
        'bbox': [100, 500, 200, 560],  # Top of column 1
    },
    {
        'id': 2,
        'text': 'Step 2',
        'color': 'green', 
        'shape': 'square',
        'bbox': [100, 400, 200, 460],  # Below step 1
    },
    {
        'id': 3,
        'text': 'Step 3',
        'color': 'green',
        'shape': 'square',
        'bbox': [280, 500, 380, 560],  # Top of column 2, same Y as step 1, X-diff=165px
    },
    {
        'id': 4,
        'text': 'Pain Point',
        'color': 'pink',
        'shape': 'star',  # Non-standard shape = pain point
        'bbox': [150, 450, 220, 510],  # Near step 2
    },
    {
        'id': 5,
        'text': 'Decision?',
        'color': 'yellow',
        'shape': 'diamond',
        'bbox': [100, 300, 200, 360],
    }
]

print("Testing parallel detection logic...\n")

# Test 1: Single-column layout (should detect parallels)
print("TEST 1: Single-column layout")
print("-" * 50)

from image_analyzer import StickyNoteAnalyzer
analyzer = StickyNoteAnalyzer()

test_notes_1 = [n.copy() for n in mock_notes]
analyzer._calculate_relationships_from_coordinates(test_notes_1, 500, 600, 'single-column')

parallel_count = len([n for n in test_notes_1 if n.get('parallel_with')])
pain_point_count = len([n for n in test_notes_1 if n.get('is_pain_point')])

print(f"Parallel steps detected: {parallel_count}")
print(f"Pain points detected: {pain_point_count}")

if parallel_count == 2:  # Steps 1 and 3 should be parallel
    print("✓ PASS: Parallel detection working in single-column mode")
else:
    print(f"✗ FAIL: Expected 2 parallel steps, got {parallel_count}")

if pain_point_count == 1:
    print("✓ PASS: Pain point identified")
else:
    print(f"✗ FAIL: Expected 1 pain point, got {pain_point_count}")

# Test 2: Newspaper layout (should NOT detect parallels)
print("\n\nTEST 2: Newspaper layout")
print("-" * 50)

test_notes_2 = [n.copy() for n in mock_notes]
analyzer._calculate_relationships_from_coordinates(test_notes_2, 500, 600, 'newspaper')

parallel_count = len([n for n in test_notes_2 if n.get('parallel_with')])
pain_point_count = len([n for n in test_notes_2 if n.get('is_pain_point')])

print(f"Parallel steps detected: {parallel_count}")
print(f"Pain points detected: {pain_point_count}")

if parallel_count == 0:
    print("✓ PASS: Parallel detection disabled in newspaper mode")
else:
    print(f"✗ FAIL: Expected 0 parallel steps in newspaper mode, got {parallel_count}")

if pain_point_count == 1:
    print("✓ PASS: Pain point identified")
else:
    print(f"✗ FAIL: Expected 1 pain point, got {pain_point_count}")

# Test 3: Pain points excluded from workflow logic
print("\n\nTEST 3: Pain points excluded from parallel detection")
print("-" * 50)

# Add another oval near step 1 at same Y-level
test_notes_3 = [n.copy() for n in mock_notes]
test_notes_3.append({
    'id': 6,
    'text': 'Another Pain',
    'color': 'red',
    'shape': 'cloud',  # Another non-standard shape
    'bbox': [250, 500, 320, 560],  # Same Y as step 1
})

analyzer._calculate_relationships_from_coordinates(test_notes_3, 500, 600, 'single-column')

pain_points = [n for n in test_notes_3 if n.get('is_pain_point')]
pain_with_parallel = [n for n in pain_points if n.get('parallel_with')]

print(f"Pain points detected: {len(pain_points)}")
print(f"Pain points with parallel_with: {len(pain_with_parallel)}")

if len(pain_with_parallel) == 0:
    print("✓ PASS: Pain points excluded from parallel detection")
else:
    print(f"✗ FAIL: Pain points should not have parallel relationships")

print("\n" + "="*50)
print("Unit test complete!")
print("="*50)
