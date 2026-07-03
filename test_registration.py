#!/usr/bin/env python3
"""
Offline tests for registration.py (T4.0 geometric registration).

No API calls, no quota — runs entirely against test_images/ fixtures.
Validated anchors (IMPL_BRIEF_T4_REGISTRATION.md): child1/2/3 close-ups
register to 24/58/82% of leftright_wholewall.jpeg width, each +/-10%.

NOTE: ASCII-only prints — stdout is cp1252 on Windows.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image

from registration import (
    register_detail_to_overview,
    transform_bbox,
    load_vision_image,
    REG_MIN_INLIERS,
)

OVERVIEW = "test_images/leftright_wholewall.jpeg"
CHILD_FIXTURES = [
    # (path, expected projected-center X as % of overview width)
    ("test_images/child1_wallcloseup.jpeg", 24.0),
    ("test_images/child2_wallcloseup.jpeg", 58.0),
    ("test_images/child3_wallcloseup.jpeg", 82.0),
]
CENTER_TOLERANCE_PCT = 10.0
UNRELATED = "test_images/newspaper_noheader_decision.jpeg"


def test_synthetic_crop():
    """Crop a known region from the overview and register it back.

    Deterministic ground truth: the projected corners of the crop must land
    within 10px of the known crop origin in Vision coordinate space.
    """
    print("\n[1] Synthetic ground truth (crop -> overview)")
    overview = load_vision_image(OVERVIEW)
    h, w = overview.shape[:2]

    crop_size = 800
    x0 = int(w * 0.30)
    y0 = int(h * 0.30)
    crop = overview[y0:y0 + crop_size, x0:x0 + crop_size]

    with tempfile.TemporaryDirectory() as tmpdir:
        crop_path = os.path.join(tmpdir, "synthetic_crop.jpeg")
        Image.fromarray(crop).save(crop_path, format='JPEG', quality=92)

        reg = register_detail_to_overview(OVERVIEW, crop_path)

    if reg['status'] != 'ok':
        print(f"  FAIL: registration failed: {reg['reason']}")
        return False

    expected = [
        [x0, y0],
        [x0 + crop_size, y0],
        [x0 + crop_size, y0 + crop_size],
        [x0, y0 + crop_size],
    ]
    max_err = 0.0
    for (px, py), (ex, ey) in zip(reg['projected_region'], expected):
        err = ((px - ex) ** 2 + (py - ey) ** 2) ** 0.5
        max_err = max(max_err, err)

    print(f"  crop origin ({x0}, {y0}), inliers={reg['inliers']}, "
          f"max corner error = {max_err:.1f}px (tolerance 10px)")
    if max_err > 10.0:
        print("  FAIL: projected corners exceed 10px tolerance")
        return False
    print("  PASS")
    return True


def test_fixture_ordering():
    """child1/2/3 must register OK with centers at 24/58/82% of width."""
    print("\n[2] Fixture ordering (child1/2/3 -> wholewall)")
    overview = load_vision_image(OVERVIEW)
    overview_w = overview.shape[1]

    all_ok = True
    for path, expected_pct in CHILD_FIXTURES:
        name = os.path.basename(path)
        reg = register_detail_to_overview(OVERVIEW, path)

        if reg['status'] != 'ok':
            print(f"  FAIL: {name}: status='failed' "
                  f"(inliers={reg['inliers']}, "
                  f"ratio={reg['inlier_ratio']:.2f}, "
                  f"reason: {reg['reason']})")
            all_ok = False
            continue

        if reg['inliers'] < REG_MIN_INLIERS:
            print(f"  FAIL: {name}: inliers {reg['inliers']} < "
                  f"{REG_MIN_INLIERS}")
            all_ok = False
            continue

        quad = np.array(reg['projected_region'])
        center_x = quad[:, 0].mean()
        center_pct = 100.0 * center_x / overview_w
        delta = abs(center_pct - expected_pct)

        status = "PASS" if delta <= CENTER_TOLERANCE_PCT else "FAIL"
        print(f"  {status}: {name}: inliers={reg['inliers']}, "
              f"ratio={reg['inlier_ratio']:.0%}, "
              f"center at {center_pct:.0f}% of width "
              f"(expected {expected_pct:.0f}% +/-{CENTER_TOLERANCE_PCT:.0f})")
        if delta > CENTER_TOLERANCE_PCT:
            all_ok = False

    return all_ok


def test_failure_gate():
    """Two unrelated fixtures must NOT produce a valid registration."""
    print("\n[3] Failure gate (unrelated images)")
    reg = register_detail_to_overview(OVERVIEW, UNRELATED)
    print(f"  status={reg['status']}, inliers={reg['inliers']}, "
          f"ratio={reg['inlier_ratio']:.2f}"
          + (f", reason: {reg['reason']}" if reg['reason'] else ""))
    if reg['status'] != 'failed':
        print("  FAIL: unrelated images produced status='ok'")
        return False
    print("  PASS")
    return True


def test_transform_bbox():
    """transform_bbox with identity and known-scale homographies."""
    print("\n[4] transform_bbox unit tests")
    bbox = [100.0, 200.0, 300.0, 400.0]

    identity = np.eye(3)
    out = transform_bbox(bbox, identity)
    if not all(abs(a - b) < 1e-6 for a, b in zip(out, bbox)):
        print(f"  FAIL: identity transform changed bbox: {out}")
        return False
    print(f"  identity: {out} == {bbox}")

    scale2 = np.diag([2.0, 2.0, 1.0])
    out = transform_bbox(bbox, scale2)
    expected = [200.0, 400.0, 600.0, 800.0]
    if not all(abs(a - b) < 1e-6 for a, b in zip(out, expected)):
        print(f"  FAIL: 2x scale transform wrong: {out} != {expected}")
        return False
    print(f"  2x scale: {out} == {expected}")
    print("  PASS")
    return True


def test_dedup_text_veto():
    """Text-dissimilarity veto for the multi-photo overlap dedup.

    Regression anchors: the 2026-07-02 TC5 run merged away two real notes
    ('Verify check #' and 'Closes invoice in Obeer') because dedup was
    purely geometric. The veto must reject those merges while still
    allowing genuine overlap duplicates (including OCR-variant and
    edge-cut empty-string readings) to dedup.
    """
    print("\n[5] Dedup text-dissimilarity veto")
    from image_analyzer import texts_clearly_dissimilar, StickyNoteAnalyzer

    must_veto = [
        # The two false positives from the 2026-07-02 TC5 run:
        ("Verify check #", "Print Checks in Doc. Printing"),
        ("Closes invoice in Obeer", "Creates outgoing Payments in Obeer"),
    ]
    must_dedup = [
        ("manual task", "manual task"),
        ("month end", "Month end no"),
        ("Over $ Limit? yes no", "Over $ Limit? no"),
        ("price discrepancy", "Price Discrepancy PO vs invoice no"),
        ("sits in an open queu in yooz", "SO is on open geru in Yooz"),
        ("", "Pay by check"),      # edge-cut "" must still dedup
        (None, "Pay by check"),
    ]

    ok = True
    for a, b in must_veto:
        if not texts_clearly_dissimilar(a, b):
            print(f"  FAIL: should veto (dissimilar): {a!r} vs {b!r}")
            ok = False
    for a, b in must_dedup:
        if texts_clearly_dissimilar(a, b):
            print(f"  FAIL: should dedup (not dissimilar): {a!r} vs {b!r}")
            ok = False

    # End-to-end through _find_overlap_duplicate: a vetoed candidate must
    # NOT match the adjacent merged note, so both notes survive.
    merged = [{'id': 1, 'bbox': [100, 100, 160, 160],
               'text': 'Verify check #', 'shape': 'square'}]
    cand = {'text': 'Print Checks in Doc. Printing', 'shape': 'square'}
    hit, _ = StickyNoteAnalyzer._find_overlap_duplicate(
        merged, cand, [110, 110, 170, 170], max_dist=45)
    if hit is not None:
        print("  FAIL: vetoed candidate still matched merged note")
        ok = False

    # ...while a genuine duplicate at the same distance must match.
    merged2 = [{'id': 1, 'bbox': [100, 100, 160, 160],
                'text': 'Hit Approve', 'shape': 'square'}]
    cand2 = {'text': 'Hit Approve', 'shape': 'square'}
    hit2, _ = StickyNoteAnalyzer._find_overlap_duplicate(
        merged2, cand2, [110, 110, 170, 170], max_dist=45)
    if hit2 is None:
        print("  FAIL: genuine duplicate did not match")
        ok = False

    # ...and a pain point ON a step must never merge (shape-class guard).
    cand3 = {'text': 'Hit Approve', 'shape': 'speech-bubble'}
    hit3, _ = StickyNoteAnalyzer._find_overlap_duplicate(
        merged2, cand3, [110, 110, 170, 170], max_dist=45)
    if hit3 is not None:
        print("  FAIL: pain point merged into standard note")
        ok = False

    if ok:
        print("  PASS")
    return ok


def main():
    print("=" * 60)
    print("T4.0 Registration Tests (offline, no API quota)")
    print("=" * 60)

    required = [OVERVIEW, UNRELATED] + [p for p, _ in CHILD_FIXTURES]
    missing = [p for p in required if not os.path.exists(p)]
    if missing:
        print(f"ERROR: missing fixtures: {missing}")
        return 1

    results = {
        'synthetic_crop': test_synthetic_crop(),
        'fixture_ordering': test_fixture_ordering(),
        'failure_gate': test_failure_gate(),
        'transform_bbox': test_transform_bbox(),
        'dedup_text_veto': test_dedup_text_veto(),
    }

    print("\n" + "=" * 60)
    failed = [name for name, ok in results.items() if not ok]
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if failed:
        print(f"\n{len(failed)} test(s) FAILED")
        return 1
    print("\nAll registration tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
