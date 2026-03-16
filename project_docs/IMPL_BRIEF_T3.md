# Implementation Brief: T3.0 — Rectangle Role Classifier
_Created: 2026-02-21 | Status: READY FOR IMPLEMENTATION_

> **Purpose**: Focused brief for Claude Code to implement T3.0 without re-reading the full backlog.
> All design decisions are finalized. Do not reopen design questions — implement as specified.
> Reference `REQUIREMENTS.md` (Rectangle Role Classification section) and `task_plan.md` (T3.0) for full rationale.

---

## What This Is

A pre-processing pass that classifies rectangular sticky notes into roles **before** layout grouping runs. Without this, banner titles and lane headers fall into the workflow sequence as process steps, breaking sequencing and PDF output.

**Three tiers:**
- **Tier 1 — Banner**: Large rectangle spanning the top of the wall. Becomes `process_title` session metadata.
- **Tier 2 — Lane Header**: First note in each group's flow direction, different color from modal color of its group. Becomes `lane_label` on the workflow group.
- **Tier 3 — Process Step**: Everything else. Sequence normally (no change to existing logic).

---

## Files to Modify

| File | Change |
|------|--------|
| `image_analyzer.py` | Add `classify_rectangle_roles()` pre-pass; call before layout grouping |
| `layout_strategies/*.py` | All grouping methods receive pre-cleaned note pool; attach `lane_label` to group dicts |
| `pdf_renderer.py` | Fix `is_rectangle_shape()` to include `'square'`; render `process_title` and `lane_label` |
| `project_docs/test_cases.md` | Document new test scenario |

**Do not modify**: `app.py` session structure, `matcher.py`, `templates/`, `REQUIREMENTS.md`, `task_plan.md`

---

## Implementation Spec

### Step 1: `classify_rectangle_roles()` in `image_analyzer.py`

Run this function on the full note pool for **every layout type** before any grouping strategy executes. It returns:
- `process_title`: string or `None`
- `lane_labels`: dict mapping group identifier → label string
- `cleaned_notes`: note pool with Tier 1 and Tier 2 notes removed

**Tier 1 Detection — Banner:**

```python
def _is_banner(note, all_notes):
    if not is_rectangle_shape(note['shape']):
        return False
    median_w = median([n['width'] for n in all_notes])
    median_h = median([n['height'] for n in all_notes])
    size_qualifies = (note['width'] >= 1.5 * median_w or
                      note['height'] >= 1.5 * median_h)
    y_in_top_20 = note['center_y'] >= 0.8 * max(n['center_y'] for n in all_notes)
    # "top 20%" means highest Y values — adjust for coordinate system if Y=0 is top
    return size_qualifies and y_in_top_20
```

> **Coordinate system note**: Confirm whether Y increases upward (ReportLab convention) or downward (image convention) in the analyzer's coordinate space. "Top of image" = highest Y in ReportLab, lowest Y in image coordinates. Adjust the `y_in_top_20` check accordingly.

Extract the first Tier 1 note found as `process_title = note['text']`. If multiple qualify, take the largest. Remove from note pool.

**Tier 2 Detection — Lane Header:**

Run after provisional grouping (needed to know which group each note belongs to). For each group:

1. Identify the "first" note in flow direction:
   - **Vertical lanes** (columns): note with the **highest Y** (topmost) in the group
   - **Horizontal lanes** (rows): note with the **lowest X** (leftmost) in the group
2. Check if that note is rectangle-shaped (`is_rectangle_shape()` — see fix below)
3. Calculate modal color = most-frequent color among the **remaining** notes in that group (excluding the candidate)
4. If candidate color ≠ modal color → **Tier 2**; set `lane_label = note['text']`; remove from note pool

**Edge cases:**
- Single note in group → Tier 3 (no modal color comparison possible)
- Candidate color matches modal color → Tier 3 (facilitator error; let Review UI handle it)
- No rectangle-shaped first note → Tier 3; no lane label for that group

---

### Step 2: Fix `is_rectangle_shape()` in `pdf_renderer.py`

Current (broken):
```python
def is_rectangle_shape(shape):
    return shape in ('rectangle', 'rectangular')
```

Fixed:
```python
def is_rectangle_shape(shape):
    return shape in ('rectangle', 'rectangular', 'square')
```

This fix must also be applied wherever `is_rectangle_shape` is called or duplicated in `image_analyzer.py` if a local copy exists there.

---

### Step 3: Thread Results Through Layout Strategies

Each layout strategy's `group_workflows()` method currently receives the full note pool. After this change:

1. `classify_rectangle_roles()` runs first, returns `cleaned_notes` and extracted metadata
2. `group_workflows()` receives `cleaned_notes` (Tier 1 and 2 already removed)
3. Each returned group dict gets a `lane_label` key populated from `lane_labels` (or `None` if no header detected)

The group dict schema extension:
```python
{
    'workflow_sequence': [...],
    'lane_label': 'Obtain PO',   # string or None
    # ... existing keys unchanged
}
```

`process_title` stored in the session payload at the top level:
```python
session['analysis']['process_title'] = 'Invoice Processing Workflow'  # or None
```

---

### Step 4: PDF Rendering in `pdf_renderer.py`

**`process_title` rendering:**
- If `session['analysis']['process_title']` is not None, render it as a **bold heading** above all lanes/columns
- Font: Helvetica-Bold, size 14 (or match existing heading style if one exists)
- Center-aligned across the full page width
- Add 12pt spacing below before the first lane/column begins

**`lane_label` rendering:**
- If a workflow group has `lane_label` set, render it as a **column or row heading** above/beside its group
- Font: Helvetica-Bold, size 11
- Position: centered above the column (vertical lanes) or left-aligned beside the row (horizontal lanes)
- Add 8pt spacing between label and first note in the group
- Use the same bounding box logic as existing column/row separators if present

These are additions — do not change any existing note rendering logic.

---

## Test Fixture Requirement

Add one new test image to `test_images/` (or create a synthetic fixture for unit testing):

**Scenario**: Two-column vertical swim lane with:
- One large banner rectangle at the top spanning both columns
- One colored square at the top of each column (different color from the other notes)
- 3–4 process steps per column in yellow squares

**Assertions** (add to `project_docs/test_cases.md` and unit test):
- `process_title` extracted correctly from banner
- Banner note NOT in `workflow_sequence` of either group
- Each column's `lane_label` populated correctly
- Lane header notes NOT in `workflow_sequence`
- Remaining process steps sequenced in correct column order
- PDF output shows bold title above all content, bold label above each column

---

## Explicit Out-of-Scope (do not implement)

- T3.1 — Parameterize thresholds (config file) — backlog
- T3.2 — Pain-point association improvements — backlog
- T3.3 — Decision branch reconvergence validation — backlog
- T3b — Low-confidence step flagging — separate task, separate brief
- Any changes to `templates/review.html` — Tier 1/2 headers don't need Review UI representation beyond what's already there
- Auto layout detection — T2.3, backlog
- Session persistence changes — T1, backlog

---

## Regression Tests to Re-Run After Implementation

```bash
python test_parallel_decision.py
python test_all_layouts.py
pytest test_delete_simple.py -q
pytest test_pain_point_rendering.py -q
```

If any test breaks, fix before committing. Do not comment out failing assertions.

---

## Commit Guidance

Commit scope: `analyzer`, then `pdf` separately if cleaner.

```
feat(analyzer): add Rectangle Role Classifier pre-pass (T3.0)

- Tier 1 (banner): size >= 1.5x median, top 20% Y position
- Tier 2 (lane header): first note in flow direction, color != modal
- Flow-direction-aware: vertical lanes use highest-Y, horizontal use lowest-X
- is_rectangle_shape() now includes 'square'
- process_title + lane_label threaded through layout strategies and PDF renderer

Refs: REQUIREMENTS.md §Rectangle Role Classification, task_plan.md T3.0
Reran: test_parallel_decision.py, test_all_layouts.py, test_pain_point_rendering.py
```
