#!/usr/bin/env python3
"""
Diagnostic script to see raw Claude response and pipeline internals.

Usage:
    python diagnose_detection.py [image_path] [flow_direction]

Defaults:
    image_path     = test_images/two_vertical_flows.jpg
    flow_direction = inferred from filename (see _LAYOUT_DEFAULTS), else vertical-swim-lanes
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_analyzer import StickyNoteAnalyzer
import json

def diagnose_image(image_path, flow_direction='vertical-swim-lanes'):
    print("="*70)
    print(f"DIAGNOSTIC: {os.path.basename(image_path)}")
    print(f"flow_direction: {flow_direction}")
    print("="*70)

    if not os.path.exists(image_path):
        print(f"FAIL: Image not found: {image_path}")
        return

    analyzer = StickyNoteAnalyzer()
    result = analyzer.analyze_workflow(image_path, flow_direction=flow_direction)

    if not result:
        print("FAIL: Analysis failed - no result returned")
        return

    # ------------------------------------------------------------------ #
    # 1. Raw JSON dump (full)
    # ------------------------------------------------------------------ #
    print("\n" + "="*70)
    print("RAW ANALYSIS RESULT (full JSON):")
    print("="*70)
    print(json.dumps(result, indent=2))

    # ------------------------------------------------------------------ #
    # 2. Every note: shape / color / center_x for lane-split diagnosis
    # ------------------------------------------------------------------ #
    print("\n" + "="*70)
    print("ALL NOTES — shape / color / geometry:")
    print("="*70)
    sticky_notes = result.get('sticky_notes', [])
    print(f"Total notes in sticky_notes: {len(sticky_notes)}")
    for note in sticky_notes:
        print(
            f"  [{note.get('id'):>2}] "
            f"shape={str(note.get('shape','?')):<14} "
            f"color={str(note.get('color','?')):<10} "
            f"cx={note.get('center_x', 0):>6.0f}  "
            f"cy={note.get('center_y', 0):>6.0f}  "
            f"text={note.get('text','')[:35]!r}"
        )

    # ------------------------------------------------------------------ #
    # 3. Tier 1 / Tier 2 classifier results
    # ------------------------------------------------------------------ #
    print("\n" + "="*70)
    print("TIER 1 / TIER 2 RESULTS:")
    print("="*70)
    print(f"process_title : {result.get('process_title')!r}")
    lane_labels = result.get('lane_labels', 'NOT IN RESULT (key missing)')
    print(f"lane_labels   : {lane_labels}")

    # ------------------------------------------------------------------ #
    # 4. Workflow / lane metadata
    # ------------------------------------------------------------------ #
    print("\n" + "="*70)
    print("WORKFLOW METADATA (lane grouping):")
    print("="*70)
    wf_meta = result.get('workflows', [])
    print(f"Number of lanes: {len(wf_meta)}")
    for wf in wf_meta:
        print(
            f"  Lane {wf.get('workflow_id')}: "
            f"{wf.get('note_count')} note(s), "
            f"label={wf.get('lane_label')!r}, "
            f"ids={wf.get('note_ids')}"
        )

    # ------------------------------------------------------------------ #
    # 5. Workflow sequence
    # ------------------------------------------------------------------ #
    seq = result.get('workflow_sequence', [])
    print(f"\nworkflow_sequence ({len(seq)} step(s)): {seq}")

    # ------------------------------------------------------------------ #
    # 6. Column gap check — tells us whether X-gap threshold is working
    # ------------------------------------------------------------------ #
    print("\n" + "="*70)
    print("COLUMN X-GAP ANALYSIS (threshold = 150 px):")
    print("="*70)
    if sticky_notes:
        xs = sorted(set(round(n.get('center_x', 0)) for n in sticky_notes))
        print(f"Unique center_x values (sorted): {xs}")
        gaps = [(xs[i+1] - xs[i], xs[i], xs[i+1]) for i in range(len(xs) - 1)]
        gaps_sorted = sorted(gaps, reverse=True)[:8]
        print("Largest gaps between adjacent X values:")
        for gap, lo, hi in gaps_sorted:
            verdict = '>>> SPLITS LANES <<<' if gap > 150 else 'same lane'
            print(f"  {lo:>6.0f} -> {hi:>6.0f}   gap = {gap:>5.0f} px   {verdict}")
    else:
        print("  (no notes to analyse)")

    # ------------------------------------------------------------------ #
    # 7. Image dimensions
    # ------------------------------------------------------------------ #
    print(f"\nImage dimensions: "
          f"{result.get('image_width', 'NOT SET')} x "
          f"{result.get('image_height', 'NOT SET')}")

    print("\n" + "="*70)
    print("DIAGNOSIS COMPLETE")
    print("="*70)


# Known test-image layout types — avoids misclassification when the second
# argument is omitted.  Add new fixtures here as they're added to test_images/.
_LAYOUT_DEFAULTS = {
    'two_vertical_flows.jpg':                    'vertical-swim-lanes',
    'leftright_headers_swimlane_painpoint.jpeg': 'horizontal-swim-lanes',
    'leftright_wholewall.jpeg':                  'horizontal-swim-lanes',
    'newspaper_1header_decision.jpeg':           'newspaper',
    'newspaper_noheader_decision.jpeg':          'newspaper',
    'child1_wallcloseup.jpeg':                   'single-column',
    'child2_wallcloseup.jpeg':                   'single-column',
    'child3_wallcloseup.jpeg':                   'single-column',
    'horizontal_brewer_cellar.jpg':              'horizontal-swim-lanes',
}

if __name__ == "__main__":
    image = (sys.argv[1] if len(sys.argv) > 1
             else "test_images/two_vertical_flows.jpg")
    if len(sys.argv) > 2:
        flow = sys.argv[2]
    else:
        basename = os.path.basename(image)
        flow = _LAYOUT_DEFAULTS.get(basename, 'vertical-swim-lanes')
        print(f"(layout auto-detected as '{flow}' from filename; "
              f"override with: python diagnose_detection.py <image> <layout>)")
    diagnose_image(image, flow)
