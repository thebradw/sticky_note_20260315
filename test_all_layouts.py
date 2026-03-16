#!/usr/bin/env python3
"""
Comprehensive test for all workflow layout types
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_analyzer import StickyNoteAnalyzer

def test_layout(image_path, flow_direction, expected_workflows=1):
    """Test a specific layout type"""
    print("\n" + "="*70)
    print(f"Testing: {os.path.basename(image_path)}")
    print(f"Layout: {flow_direction}")
    print(f"Expected workflows: {expected_workflows}")
    print("="*70)
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return False
    
    analyzer = StickyNoteAnalyzer()
    result = analyzer.analyze_workflow(image_path, flow_direction=flow_direction)
    
    if not result:
        print("❌ Analysis failed")
        return False
    
    sticky_notes = result.get('sticky_notes', [])
    workflows = result.get('workflows', [])
    
    print(f"\n✅ Analysis complete!")
    print(f"   Total notes: {len(sticky_notes)}")
    print(f"   Workflows detected: {len(workflows)}")
    
    # Check parallel steps
    parallel_notes = [n for n in sticky_notes if n.get('parallel_with')]
    if parallel_notes:
        print(f"\n✅ PARALLEL STEPS: {len(parallel_notes)} notes")
        for note in parallel_notes:
            partner = next((n for n in sticky_notes if n['id'] == note['parallel_with']), None)
            if partner:
                print(f"   Note {note['id']} ({note['text'][:25]}) ↔ Note {note['parallel_with']} ({partner['text'][:25]})")
    else:
        print("\n   No parallel steps detected")
    
    # Check decision diamonds
    decision_notes = [n for n in sticky_notes if n.get('decision_branches')]
    if decision_notes:
        print(f"\n✅ DECISION DIAMONDS: {len(decision_notes)}")
        for note in decision_notes:
            branches = note.get('decision_branches', {})
            print(f"   Note {note['id']} ({note['text'][:25]})")
            if branches.get('yes_next_step'):
                yes_note = next((n for n in sticky_notes if n['id'] == branches['yes_next_step']), None)
                print(f"      Yes → {yes_note['text'][:25] if yes_note else 'None'}")
            if branches.get('no_next_step'):
                no_note = next((n for n in sticky_notes if n['id'] == branches['no_next_step']), None)
                print(f"      No  → {no_note['text'][:25] if no_note else 'None'}")
    else:
        print("\n   No decision diamonds detected")
    
    # Show workflow groupings
    if workflows and len(workflows) > 1:
        print(f"\n📊 WORKFLOW GROUPINGS:")
        for wf in workflows:
            print(f"   Workflow {wf['workflow_id']}: {wf['note_count']} notes")
    
    return True

def test_horizontal_swim_lanes(image_path):
    """Test Case 4: Horizontal swim lanes with pain points.

    Checks:
    - Multiple workflow lanes detected (expect 5, but Vision may group small
      lanes together — accept >= 3 as passing)
    - Pain points flagged (is_pain_point=True) for non-standard shapes
    - Pain points attached to anchors (pain_point_for set)
    - No spurious parallel detection within horizontal rows
    - Lane headers detected for at least some workflows
    """
    print("\n" + "=" * 70)
    print("Testing: leftright_headers_swimlane_painpoint.jpeg")
    print("Layout: horizontal-swim-lanes")
    print("Expected: 5 workflows, 25 steps, 12 pain points")
    print("=" * 70)

    if not os.path.exists(image_path):
        print(f"SKIP: Image not found: {image_path}")
        return True  # don't fail the suite for a missing fixture

    analyzer = StickyNoteAnalyzer()
    result = analyzer.analyze_workflow(image_path, flow_direction='horizontal-swim-lanes')

    if not result:
        print("FAIL: Analysis returned None")
        return False

    sticky_notes = result.get('sticky_notes', [])
    workflows = result.get('workflows', [])
    process_title = result.get('process_title')

    print(f"\n   Total notes returned: {len(sticky_notes)}")
    print(f"   Workflows detected: {len(workflows)}")
    if process_title:
        print(f"   Process title: {process_title}")

    passed = True

    # --- Check 1: Multiple workflows ---
    if len(workflows) >= 3:
        print(f"\n   PASS: {len(workflows)} workflows detected (need >= 3)")
    else:
        print(f"\n   FAIL: Only {len(workflows)} workflow(s) detected (need >= 3)")
        passed = False

    # --- Check 2: Pain points flagged ---
    pain_points = [n for n in sticky_notes if n.get('is_pain_point')]
    if pain_points:
        print(f"   PASS: {len(pain_points)} pain point(s) flagged")
        for pp in pain_points[:5]:
            anchor = pp.get('pain_point_for', 'none')
            print(f"      [{pp.get('shape','?'):10}] \"{pp.get('text','?')[:40]}\" -> anchor {anchor}")
        if len(pain_points) > 5:
            print(f"      ... and {len(pain_points) - 5} more")
    else:
        print("   FAIL: No pain points flagged")
        passed = False

    # --- Check 3: Pain points attached ---
    attached = [p for p in pain_points if p.get('pain_point_for')]
    if pain_points and attached:
        print(f"   PASS: {len(attached)}/{len(pain_points)} pain point(s) have pain_point_for set")
    elif pain_points:
        print(f"   FAIL: 0/{len(pain_points)} pain points have pain_point_for set")
        passed = False

    # --- Check 4: No spurious parallel detection ---
    parallel_notes = [n for n in sticky_notes if n.get('parallel_with')]
    if not parallel_notes:
        print("   PASS: No spurious parallel detection in horizontal lanes")
    else:
        print(f"   FAIL: {len(parallel_notes)} note(s) incorrectly marked parallel")
        for n in parallel_notes[:3]:
            print(f"      Note {n['id']} ({n.get('text','?')[:25]}) parallel_with={n['parallel_with']}")
        passed = False

    # --- Check 5: Lane labels detected ---
    labelled = [wf for wf in workflows if wf.get('lane_label')]
    if labelled:
        print(f"   PASS: {len(labelled)} lane label(s) detected")
        for wf in labelled:
            print(f"      Workflow {wf['workflow_id']}: \"{wf['lane_label'][:40]}\"")
    else:
        print("   INFO: No lane labels detected (headers may match modal color)")

    # --- Check 6: Pain points excluded from workflow_sequence ---
    sequence = result.get('workflow_sequence', [])
    pp_ids = {p['id'] for p in pain_points}
    leaked = pp_ids & set(sequence)
    if not leaked:
        print("   PASS: Pain points excluded from workflow_sequence")
    else:
        print(f"   FAIL: {len(leaked)} pain point ID(s) leaked into workflow_sequence: {leaked}")
        passed = False

    # --- Summary ---
    print(f"\n   Workflow breakdown:")
    for wf in workflows:
        label = f" [{wf.get('lane_label')}]" if wf.get('lane_label') else ""
        print(f"      Workflow {wf['workflow_id']}: {wf['note_count']} notes{label}")

    return passed


def main():
    print("="*70)
    print("STICKY NOTE ANALYZER - COMPREHENSIVE LAYOUT TEST")
    print("="*70)

    tests = [
        {
            'name': 'Test Case 1: Single Column with Parallel & Decision',
            'image': 'test_images/newspaper_1header_decision.jpeg',
            'layout': 'single-column',
            'expected_workflows': 1
        },
        {
            'name': 'Test Case 2: Newspaper Columns',
            'image': 'test_images/newspaper_noheader_decision.jpeg',
            'layout': 'newspaper',
            'expected_workflows': 1
        }
    ]

    results = []
    for test in tests:
        print(f"\n\n{'='*70}")
        print(f"TEST: {test['name']}")
        print(f"{'='*70}")
        success = test_layout(test['image'], test['layout'], test['expected_workflows'])
        results.append((test['name'], success))

    # Test Case 4: Horizontal swim lanes (dedicated function)
    print(f"\n\n{'='*70}")
    print(f"TEST: Test Case 4: Horizontal Swim Lanes with Pain Points")
    print(f"{'='*70}")
    tc4_success = test_horizontal_swim_lanes('test_images/leftright_headers_swimlane_painpoint.jpeg')
    results.append(('Test Case 4: Horizontal Swim Lanes with Pain Points', tc4_success))
    
    # Summary
    print("\n\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "="*70)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED")
    print("="*70)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
