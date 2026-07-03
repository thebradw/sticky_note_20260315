# Implementation Brief: T4.0 — Geometric Registration for Multi-Photo Stitching
_Created: 2026-07-02 | Status: READY FOR IMPLEMENTATION_

> **Purpose**: Focused brief for Claude Code to implement T4.0 without re-reading the full backlog.
> All design decisions are finalized. Do not reopen design questions — implement as specified.
> This brief SUPERSEDES task_plan.md T2.2 ("Multi-photo matching tuning"). Do not tune
> `calculate_match_confidence` weights — that path is now fallback-only.

---

## What This Is

The multi-photo path currently matches detail-photo notes to overview notes using a fuzzy
confidence score (color 20 + shape 20 + coarse grid position 30 + text 30). On wide horizontal
walls this fails structurally: overview text is unreadable (so 30 points drop out), the position
grid is ~5x5 (so dozens of notes share a cell), and most notes are the same color and shape.
No amount of weight tuning fixes this, because nothing in the system establishes where each
detail photo physically sits within the overview.

T4.0 adds that missing step. OpenCV SIFT feature matching computes a homography per detail
photo that maps its pixel coordinates into overview pixel space. Detail note bboxes transform
deterministically into overview coordinates, and matching becomes nearest-neighbor by distance.
Text becomes payload carried from the detail photo, never a matching signal.

**Validated on repo fixtures (2026-07-02, SIFT nfeatures=8000, working res 2400px):**

| Detail photo | Inliers | Inlier ratio | Center lands at | Physical position | Time |
|---|---|---|---|---|---|
| child1_wallcloseup.jpeg | 524 | 81% | 24% of overview width | Left column | 1.7s |
| child2_wallcloseup.jpeg | 63 | 32% | 58% of overview width | Middle column | 1.4s |
| child3_wallcloseup.jpeg | 53 | 28% | 82% of overview width | Right column | 1.4s |

All three register in correct left-to-right order at zero API cost. Note: ORB was tested and
rejected — it produced a false homography on child3. Use SIFT.

**Second payoff — pipeline unification.** `process_multi_photo_session` Step 5 currently sorts
merged notes by grid_position and bypasses the entire single-photo pipeline: no
`classify_rectangle_roles` (T3.0), no layout strategies, no parallel or decision detection.
After T4.0, merged notes carry real pixel bboxes in one overview coordinate space, so they
route through the SAME pipeline as single-photo analysis. Wall-scale workflows inherit every
heuristic already validated in TC1–TC4 without code duplication.

---

## Files to Modify

| File | Change |
|------|--------|
| `registration.py` | **NEW** — pure geometry: image loading, SIFT, homography, bbox transforms |
| `image_analyzer.py` | Update `analyze_overview` prompt to return pixel bboxes; rewrite Steps 3.5–5 of `process_multi_photo_session` |
| `matcher.py` | Add `match_by_geometry()`; keep `match_detail_to_overview()` unchanged as fallback |
| `requirements.txt` | **NEW** — repo has no requirements file; create one including `opencv-python-headless` and `numpy` |
| `test_registration.py` | **NEW** — offline unit tests, no API quota required |
| `project_docs/test_cases.md` | Add Test Case 5: multi-photo horizontal wall |

**Do not modify**: `layout_strategies/*` (they consume the unified note pool as-is),
`pdf_renderer.py`, `templates/`, `app.py` session structure, the legacy matcher scoring logic.

---

## Implementation Spec

### Step 1: `registration.py` (new module)

**Coordinate space rule (critical):** Vision bboxes are expressed in the resized image submitted
to the API (max 4000px, via the existing resize helper in `image_analyzer.py`). Registration
MUST load images through that same resize path so every image has exactly one coordinate space.
No scale composition, no second bookkeeping system.

```python
# Config constants (top of registration.py)
REG_MAX_FEATURES        = 8000
REG_LOWE_RATIO          = 0.75
REG_RANSAC_REPROJ       = 5.0
REG_MIN_INLIERS         = 30     # child3 (weakest fixture) scored 53
REG_MIN_INLIER_RATIO    = 0.20
REG_MATCH_MAX_DIST_FACTOR = 0.75 # x median overview note width
```

```python
def register_detail_to_overview(overview_path, detail_path) -> dict:
    """
    Returns {
        'status': 'ok' | 'failed',
        'homography': 3x3 np.ndarray or None,
        'inliers': int,
        'inlier_ratio': float,
        'projected_region': [[x,y] x4] or None,  # detail corners in overview space
        'reason': str  # populated when status == 'failed'
    }
    """
```

Pipeline inside: load both images grayscale through the Vision resize helper →
`cv2.SIFT_create(nfeatures=REG_MAX_FEATURES)` → `BFMatcher(NORM_L2).knnMatch(k=2)` →
Lowe ratio test at 0.75 → `cv2.findHomography(src, dst, cv2.RANSAC, REG_RANSAC_REPROJ)`.

> **Implementation refinement (2026-07-02, approved):** SIFT detection, matching, and the
> inlier gates run on internal working copies downscaled to 2400px max dimension
> (`REG_DETECT_MAX_DIM`) — the resolution the gate constants above were calibrated at.
> At the full 4000px Vision resolution the Lowe-ratio match pool is larger, so inlier
> ratios drop below `REG_MIN_INLIER_RATIO` even for geometrically correct homographies
> (child2 scored 0.196, child3 0.166 at 4000px; both pass at 2400px). The RANSAC result
> is composed into Vision bbox space via per-image scale factors measured from actual
> post-thumbnail dimensions: `H_4000 = inv(S_overview) @ H_2400 @ S_detail` with
> `S = diag(scale, scale, 1)`. Callers only ever see Vision-space (4000px) coordinates —
> the one-coordinate-space rule for bboxes is unchanged; only the detection resolution
> is decoupled. Validated post-composition: synthetic crop ground truth lands within
> 0.7px; child1/2/3 register at 24/58/82% of overview width with 480/57/45 inliers.

**Acceptance gates (all must pass, else status='failed'):**
1. `inliers >= REG_MIN_INLIERS`
2. `inlier_ratio >= REG_MIN_INLIER_RATIO`
3. Projected detail corners form a convex quadrilateral with positive area
4. Projected region center lies within overview image bounds

```python
def transform_bbox(bbox, H) -> list:
    """Transform [x1,y1,x2,y2] via H: project all 4 corners, return
    axis-aligned [min_x, min_y, max_x, max_y] in overview space."""
```

### Step 2: `analyze_overview` prompt change in `image_analyzer.py`

Rewrite the overview prompt to return the SAME bbox schema as `analyze_workflow`:
pixel-precise `bbox: [x1,y1,x2,y2]` per note, plus color and shape. Text is best-effort:
instruct Vision to return `""` for unreadable notes rather than guessing (keep the fictional
example-text rule from the 2026-03-14 prompt hardening). Keep `readability_score`. Because
text is no longer required, drop the exhaustive-text instructions — this shortens responses
and reduces the truncation risk on 40+ note walls.

Keep populating `position` strings and `grid_position` for now — the fallback path still
consumes them. Remove nothing from `matcher.py`.

### Step 3: `match_by_geometry()` in `matcher.py`

```python
def match_by_geometry(self, overview_notes, detail_notes_transformed, max_dist) -> dict:
    """
    detail_notes_transformed carry 'overview_bbox' and derived center in overview space.
    Greedy one-to-one assignment by ascending center-to-center distance.
    Accept pair if distance <= max_dist. Color/shape used ONLY as tie-breakers
    when two candidates are within 15% distance of each other.
    Returns same schema as match_detail_to_overview: matches / unmatched_overview /
    unmatched_detail / conflicts (conflicts will normally be empty on this path).
    """
```

`max_dist = REG_MATCH_MAX_DIST_FACTOR * median(overview note widths)`.

Merged note rule: keep overview `id` and overview-space bbox; take text, color, shape from
the detail note (it is the higher-resolution observation). Set `source='registered'` and
`confidence = min(99, 60 + inlier_ratio * 40)`.

**Unmatched detail notes with a valid registration are NEW notes, not errors.** The overview
pass truncates or misses notes on dense walls; a registered detail photo proves where the
note physically sits. Insert them into the pool with their transformed overview bbox,
`source='detail_registered'`, confidence 85.

### Step 4: Rewire `process_multi_photo_session` in `image_analyzer.py`

Replace Steps 3.5–5 with:

```python
# Step 3.5 — register each detail photo
for detail_path, detail_result in zip(detail_paths, detail_results):
    reg = register_detail_to_overview(overview_path, detail_path)
    if reg['status'] == 'ok':
        for note in detail_result['sticky_notes']:
            note['overview_bbox'] = transform_bbox(note['bbox'], reg['homography'])
        registered_notes.extend(...)
    else:
        print(f"Registration failed for {detail_path}: {reg['reason']} — legacy matcher fallback")
        fallback_notes.extend(detail_result['sticky_notes'])

# Step 4a — geometric matching for registered notes (primary path)
# Step 4b — legacy match_detail_to_overview for fallback_notes only;
#           cap their confidence at 60 and flag low_confidence=True

# Step 5 — UNIFIED PIPELINE (replaces grid_position sorting entirely)
# Recompute center_x/center_y/width/height from overview-space bboxes, then call the
# same sequence the single-photo path uses: classify_rectangle_roles ->
# layout strategy group_workflows/sort_workflow -> parallel + decision detection.
```

If EVERY detail photo fails registration, the entire session falls back to the current
behavior unchanged. Nothing regresses.

---

## Test Requirements

### `test_registration.py` (offline — no API calls, runs in CI/regression)

1. **Synthetic ground truth**: crop a known 800px region from
   `test_images/leftright_wholewall.jpeg`, register crop→overview, assert the projected
   corners land within 10px of the known crop origin. Deterministic proof of correctness.
2. **Fixture ordering**: register child1/2/3 against the wholewall overview; assert all
   three return `status='ok'` with `inliers >= 30`, and their projected centers fall at
   24% / 58% / 82% of overview width, each ±10%.
3. **Failure gate**: register two unrelated fixtures (e.g., `newspaper_noheader_decision.jpeg`
   against `leftright_wholewall.jpeg`); assert `status='failed'`.
4. **transform_bbox**: unit test with an identity and a known-scale homography.

### Test Case 5 in `project_docs/test_cases.md` (API integration, manual run)

Fixture set: `leftright_wholewall.jpeg` (overview) + child1/2/3 (details), layout
`horizontal-swim-lanes`. Assertions: no duplicate notes (no two merged notes with center
distance < 0.5 x median note width), workflow_sequence ordering consistent with left→right
wall order, text for registered notes sourced from detail photos, T3.0 headers elected.

---

## Explicit Out-of-Scope (do not implement)

- Tuning `calculate_match_confidence` weights — path is deprecated to fallback-only
- Arrow-follow overrides (old T2.2 sub-item) — backlog, separate task
- Session persistence (T1) — separate task, still blocking for Render deployment
- Auto layout detection (T2.3) — backlog
- Full panoramic image stitching (blending pixels into one composite image) — NOT needed;
  we register coordinates, we never need a stitched picture
- Review UI conflict panel changes (T4.1 in task_plan) — geometric path rarely conflicts
- Removing `position` strings / `grid_position` — needed by the fallback path

---

## Regression Tests to Re-Run After Implementation

```bash
python test_registration.py          # new, offline
python test_parallel_decision.py
python test_all_layouts.py
pytest test_delete_simple.py test_pain_point_rendering.py -q
```

Single-photo paths must be byte-identical in behavior — this change touches only the
multi-photo branch of `process_multi_photo_session` plus the overview prompt.

---

## Commit Guidance

```
feat(analyzer): geometric registration for multi-photo stitching (T4.0)

- New registration.py: SIFT + RANSAC homography, detail->overview coordinate transform
- analyze_overview now returns pixel bboxes (same schema as analyze_workflow)
- match_by_geometry: nearest-neighbor assignment in overview space; fuzzy matcher
  retained as fallback when registration fails
- Multi-photo notes now route through classify_rectangle_roles + layout strategies
  (previously bypassed the entire single-photo pipeline)
- Validated on wall fixtures: child1/2/3 register at 24/58/82% of overview width

Refs: IMPL_BRIEF_T4_REGISTRATION.md; supersedes task_plan.md T2.2
Reran: test_registration.py, test_parallel_decision.py, test_all_layouts.py,
test_delete_simple.py, test_pain_point_rendering.py
```

---

## Approved Post-Implementation Refinements (2026-07-02)

Documented in the same spirit as the Step 1 detection-resolution note: these are
approved deviations from the original spec above, discovered during Test Case 5
live validation.

### Vision coordinate space is computed per-image, not "max 4000px"

The coordinate-space rule's original wording ("the resized image submitted to
Vision, max 4000px") was empirically false: Claude resizes images server-side
(high-resolution tier: 2576px long edge AND 4784 visual tokens at
`ceil(w/28) * ceil(h/28)`) and reports bboxes in THAT space. TC5 showed overview
bboxes compressed to ~55% of the submitted 4000px frame. Fix:
`vision_resized_size()` in `image_analyzer.py` (Anthropic's reference algorithm,
verbatim) computes the exact per-image dimensions; `encode_image()` and
`registration._load_vision_pil()` both resize to those dimensions, so submitted
pixels equal model-seen pixels by construction. For 4032x3024 fixtures the TOKEN
limit binds (Vision space 2212x1659) — the effective dimension is aspect-ratio
dependent and must never be hardcoded.

### Acceptance gates: statistical floors + geometric plausibility

OpenCV 5.0's RANSAC is deterministically seeded, so gate calibration is against
exact fixture values (10 runs bit-identical). Measured at the computed Vision
dimensions, the match statistics cannot separate genuine from impostor pairs:
the unrelated-pair fixture scores MORE inliers (39) than the weakest genuine
pair (child3, 36) and its ratio sits 0.0044 below it. `REG_MIN_INLIERS` (30) and
`REG_MIN_INLIER_RATIO` (0.15, was 0.20) are therefore sanity floors only; the
load-bearing impostor rejector is a plausibility gate on the projected
detail-region quad: convex + positive area, area fraction of overview in
[0.02, 1.5], per-edge scale spread <= 1.6 (genuine fixtures: area 0.079-0.240,
spread <= 1.15; impostor: collapsed non-convex quad, spread 1.80). Full
empirical basis in the `registration.py` constants block.

