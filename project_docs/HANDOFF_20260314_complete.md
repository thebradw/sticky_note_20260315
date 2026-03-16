# Handoff — Session 2026-03-14

## Status
Active development on Test Case 4 (horizontal swim lanes, 5 workflows, 25 steps, 12 pain points).
All changes below are deployed. **Horizontal swim lane header detection is awaiting a clean end-to-end test.**

---

## What Was Broken at Start of Session
The PDF output for `leftright_headers_swimlane_painpoint.jpeg` was unusable: wrong workflow titles, wrong note counts per lane, a hallucinated process step appearing 8+ times, and the Review UI too scrambled to hand-edit. Root cause investigation found five compounding bugs across two sessions.

---

## Changes Made

### 1. Vision prompt — example JSON text replaced with fictional terms
**File:** `image_analyzer.py`

The JSON schema example in the Vision prompt contained real test case content ("Sales Order Data Flow", "Auto fills PO when works", "If fails do manually", etc.). Vision was using these as fill-in text for unreadable handwriting, causing hallucinated strings to appear repeatedly in the PDF output.

**Fix:** All example text replaced with clearly fictional terms: "Zyphon Routing Loop", "Grimbolt intake", "Flurex check", "Vondra staging", "Dispatch to Flurex bin", "Reroute via Grimbolt".

---

### 2. Vision prompt — horizontal swim lane header detection instructions
**File:** `image_analyzer.py`

The horizontal swim lanes prompt block lacked explicit guidance for identifying workflow title stickies. Vision was not setting any distinguishing flags on header notes.

**Fix:** Added a `WORKFLOW TITLE STICKIES` block with four testable signals and an `is_workflow_title: true` instruction. Added a `PAIN POINTS` block naming "speech-bubble" and "callout" as explicit shape values. Added `is_workflow_title` to the JSON schema example.

---

### 3. Vision prompt — color judgment relative to other notes
**File:** `image_analyzer.py`

On warm-toned walls (terracotta, tan, dark wood), Vision was reporting yellow header stickies as "orange" or "salmon" because it was comparing against the wall background rather than the other stickies.

**Fix:** Added explicit instruction for Vision to judge colors relative to other notes on the board, not the wall. Specific callout against reporting yellow as orange on warm-toned walls.

---

### 4. `classify_rectangle_roles` — T3.0 gap threshold mismatch (horizontal)
**File:** `image_analyzer.py`

`classify_rectangle_roles` used `img_height * 0.15` (cap 100px) for the provisional Y-row grouping threshold. `HorizontalSwimLaneStrategy.group_workflows` uses `img_height * 0.08` (cap 90px). At img_height=960 that is 100px vs 77px — a 30% difference. T3.0's provisional row groups were misaligned with the actual lane groups, so the leftmost-note candidates were wrong and no headers were being detected.

**Fix:** Changed T3.0's `LANE_GAP_HORIZONTAL` formula to `max(40, min(90, img_height * 0.08))` — identical to the actual strategy.

---

### 5. `classify_rectangle_roles` — pain points polluting T3.0 provisional Y-sort
**File:** `image_analyzer.py`

T3.0's provisional Y-grouping included all notes, including pre-flagged pain points. Pain points sit below their anchor steps, physically in the gap between horizontal lanes. They were bridging inter-lane gaps and preventing clean row splits — the same problem `HorizontalSwimLaneStrategy` avoids by stripping pain points before gap detection.

**Fix:** T3.0's horizontal provisional grouping now filters out `is_pain_point=True` notes before sorting, matching what the actual strategy does. Notes with non-standard shapes are pre-flagged as `is_pain_point` before T3.0 runs (this pre-flag pass was already in place).

---

### 6. `classify_rectangle_roles` — pain point mis-classified as square becomes header candidate
**File:** `image_analyzer.py`

The post-group Tier 2 pass and the T3.0 provisional pass both select the leftmost note in each lane as the header candidate. If Vision mis-classifies a pain point (speech-bubble, callout) as `shape='square'`, it passes `is_rectangle_shape` and can be picked up as the lane label. This is how `'no white house brew in a box'` (a pain point) appeared as the label for lane 1.

**Fix:** Both passes now check `candidate.get('is_pain_point')` immediately after `is_rectangle_shape` and skip the candidate if it is flagged.

---

### 7. `classify_rectangle_roles` — Tier 1 banner disabled for horizontal swim lanes
**File:** `image_analyzer.py`

Tier 1 banner detection scans the top 20% of the image for a note that is ≥1.5× the median size. In a horizontal swim lane image the "top 20%" is the first swim lane — full of regular process steps. One step with a slightly larger bounding box was crossing the 1.5× threshold and being promoted to the workflow title (`"manual check to log"` in Test Case 4).

Vertical swim lanes are unaffected: their column headers are physically at the top of the image so Tier 1 works correctly there.

**Fix:** Tier 1 banner detection is skipped when `flow_direction == 'horizontal-swim-lanes'`. All other layouts (single-column, newspaper, vertical-swim-lanes) retain the existing Tier 1 logic. Console prints `[T3.0] Tier 1 banner skipped (horizontal swim lanes use Tier 2 lane headers only)` to confirm.

---

### 8. Diagnostic logging added to T3.0 horizontal Tier 2 pass
**File:** `image_analyzer.py`

When T3.0 removed 0 headers it was impossible to tell from the console whether the failures were due to shape rejection, is_pain_point, color contrast, or spatial gap ratio.

**Fix:** Each candidate note now logs its text, shape, color, and `is_workflow_title` flag before evaluation. Color-contrast misses print both the candidate color and the modal. Spatial gap passes print the first-gap, median-gap, and ratio (with the 1.80× threshold clearly shown). Shape and pain-point rejections each have their own log lines.

---

### 9. `notes_similar` — spatial proximity gate
**File:** `image_analyzer.py`

The deduplication check was comparing text similarity (≥80%) only. Two notes with similar text in different swim lanes (e.g., both saying "Manual") would be collapsed into one, silently dropping a legitimate process step.

**Fix:** Added a 60px center-distance gate — both text similarity ≥80% AND center distance ≤60px must be true for deduplication to fire.

---

### 10. `_flag_low_confidence_text` — hallucination signal
**File:** `image_analyzer.py`

Short notes (1–3 words) whose vocabulary shares nothing with the rest of the note pool are flagged `low_confidence: True`. These are likely Vision hallucinations on unreadable stickies.

---

### 11. `review.html` — low-confidence badge
**File:** `templates/review.html`

Notes flagged `low_confidence` now display a yellow "⚠️ Verify" badge in the Review UI so facilitators can confirm or correct them without needing to inspect every note.

---

### 12. `max_tokens` layout-aware increase
**File:** `image_analyzer.py`

For horizontal swim lanes and newspaper layouts (high note count, complex spatial relationships) `max_tokens` was raised to 12,000. Other layouts remain at 8,192 to avoid unnecessary cost.

---

## Awaiting Test

**Test Case 4 — horizontal swim lanes** (`leftright_headers_swimlane_painpoint.jpeg`)

Expected outcome after all fixes:
- No workflow title at the top (Tier 1 banner suppressed)
- 5 lane labels detected: "Data Flow", "Prod. Data Flow", "Prod. Sched. Data", "Sales Order Data Flow", "Forecast Data Flow"
- Note distribution roughly: 4 / 10 / 1 / 7 / 3 (per test_cases.md)
- 12 pain points attached to their anchor steps
- Console shows `[T3.0] Tier 1 banner skipped` and 5 Tier 2 header lines

**Test Case — vertical swim lanes** (regression check after change 7)
- Should behave identically to pre-session baseline; Tier 1 active as before

---

## Known Remaining Issues (not addressed this session)
- OCR misread: `'SSA print Lot data to Azure'` should be `'QSA pushes Lot data to Azure'` — Pass 2 crop-OCR misread. Not a code bug; re-shoot or manual correction in Review UI.
- Color as header designator deliberately excluded from design. Headers are detected by `is_workflow_title` flag + spatial isolation. If Vision fails to set `is_workflow_title` on an ambiguous layout, spatial isolation is the fallback — review the T3.0 diagnostic log to confirm ratio.
