# CLAUDE.md — Sticky Note Workflow Processor

## What This Project Does
Converts 1–6 smartphone photos of sticky-note process maps into structured PDF process maps. Photos → Claude Vision OCR → layout heuristics → reviewer UI → PDF. Supports single column, newspaper columns, horizontal swim lanes, and vertical swim lanes.

## Key Reference Docs (read before touching related code)
| Doc | When to read it |
| --- | --- |
| `project_docs/REQUIREMENTS.md` | Before changing any analyzer heuristic or detection threshold |
| `project_docs/ARCHITECTURE.md` | System flow, component breakdown, and known fixes applied |
| `project_docs/SOLUTION_ARCHITECTURE.md` | Full function/method/dependency inventory for `app.py`, `image_analyzer.py`, `matcher.py` |
| `project_docs/COMPONENT_MAP.md` | Quick maturity/ownership table per component |
| `project_docs/test_cases.md` | Canonical regression scenarios — run these after any layout or PDF change |
| `project_docs/PRD.md` | Product intent, KPIs, personas, and out-of-scope items |
| `project_docs/task_plan.md` | **BACKLOG ONLY** — planned work, not current functionality |
| `project_docs/PAIN_POINT_SHAPES.md` | When working on shape detection or pain point logic |
| `project_docs/NEWSPAPER_LAYOUT_REFERENCE.md` | When working on newspaper column layout strategy |
| `project_docs/TROUBLESHOOTING.md` | When debugging PDF generation or Flask startup failures |
| `project_docs/IMPL_BRIEF_T3.md` | Reference for T3.0 rectangle role classifier logic (implemented 2026-03) |
| `project_docs/IMPL_BRIEF_T4_REGISTRATION.md` | When implementing T4.0 geometric registration for multi-photo stitching (ready-for-implementation brief) |
| `project_docs/USER_STORIES.md` | Supplementary product context — read alongside PRD.md |
| `project_docs/AGENTS.md` | Supplementary repo guidelines — overlaps with this file; check for conflicts |
| `project_docs/archive/` | Historical fix summaries — read only for decision branch archaeology |

## Run & Test Commands
```bash
# Start the app
python app.py
# Browse to http://localhost:5000

# Debug a single image's raw Claude Vision response
python diagnose_detection.py test_images/<file>.jpeg

# Smoke-test flow merging, diamonds, parallel arrows (no web tier)
python test_parallel_decision.py
python test_all_layouts.py

# Flask endpoint regression tests (canonical suites only)
pytest test_delete_simple.py test_pain_point_rendering.py -q

# API connectivity check (cycles model names until one responds)
python test_api.py

# Offline testing without Anthropic quota
python mock_analyzer.py
```

## Slash Commands (use in Claude Code)
- `/diagnose <filename.jpeg>` — dump raw Vision response for a single test image
- `/smoke` — run both smoke-test scripts in sequence
- `/regression` — run the canonical pytest suite

## Project Structure
```
app.py                  — Flask routes + session management + PDF orchestration
pdf_renderer.py         — ProcessMapFlowable (ReportLab PDF drawing, extracted from app.py)
image_analyzer.py       — StickyNoteAnalyzer (Claude Vision calls, layout heuristics)
matcher.py              — NoteMatcherSystem (geometric note assignment; legacy fuzzy matcher as fallback)
registration.py         — SIFT/RANSAC homography: maps detail-photo coordinates into overview space (T4.0)
mock_analyzer.py        — Offline stub for testing without Anthropic quota
layout_strategies/      — Pluggable grouping/sorting per layout type (see local CLAUDE.md)
templates/              — Jinja UI (index, analysis progress, review editor)
test_images/            — 7 canonical JPEG fixtures — DO NOT MODIFY (protected by settings.json)
uploads/                — Runtime session artifacts (transient, not stable references)
outputs/                — Generated PDFs (populated by /generate-pdf)
project_docs/           — Reference documentation (see Key Reference Docs table above)
project_docs/archive/   — Historical fix summaries — not active documentation
.claude/commands/       — Custom slash commands: /diagnose, /smoke, /regression
```

## Test File Status
**Canonical (run these):** `test_delete_simple.py`, `test_pain_point_rendering.py`, `test_parallel_decision.py`, `test_all_layouts.py`, `test_registration.py` (after T4.0)
**Scratch / superseded (do not rely on):** `test.py`, `test_delete.py`, `test_delete_comprehensive.py`

## Coding Conventions
- **Style**: PEP 8, 4-space indents
- **Functions**: `snake_case` (e.g., `analyze_workflow`)
- **Classes**: `PascalCase` (e.g., `ProcessMapFlowable`)
- **Dict keys**: Reflect analyzer payloads (e.g., `parallel_with`, `decision_branches`)
- Prefer small pure helpers over long procedural blocks
- Guard file writes with `os.path` checks
- Reuse existing logging/print patterns in CLI scripts

## Spatial Thresholds (don't change without updating `REQUIREMENTS.md`)
```python
PARALLEL_Y_TOLERANCE = 30      # px — Y-diff for parallel detection
LANE_GAP_HORIZONTAL  = 100     # px — gap between horizontal swim lanes
LANE_GAP_VERTICAL    = 150     # px — gap between vertical swim lanes
DECISION_YES_MIN_X   = 50      # px — min distance right for Yes branch
DECISION_NO_MIN_Y    = 50      # px — min distance down for No branch
```

## Testing Guidelines
- Use standalone scripts (`test_parallel_decision.py`, `test_all_layouts.py`) for visual/layout logic
- Use pytest for Flask route and pure-helper regressions
- After changing a heuristic: capture JSON diff via `diagnose_detection.py`, drop fixture under `test_images/`, document scenario in `project_docs/test_cases.md`
- Tests should assert note counts, branch links, and `workflow_sequence` ordering — not just success logs
- Offline testing without Anthropic quota: use `mock_analyzer.py`

## Multi-Photo Architecture Rules (T4.0)

Geometric registration is the primary matching path for multi-photo sessions. `registration.py` computes a SIFT/RANSAC homography per detail photo and transforms detail note bboxes into overview pixel coordinates; `matcher.match_by_geometry` then assigns notes by nearest-neighbor distance. Design rules that must hold:

1. **One coordinate space per image.** All bboxes live in the resized image submitted to Vision (max 4000px). Registration loads images through the same resize helper. Never introduce a second coordinate bookkeeping system.
2. **Text is payload, never a matching signal.** Detail photos supply text; the overview supplies position. Do not reintroduce text similarity into primary matching.
3. **The fuzzy matcher (`match_detail_to_overview`) is fallback-only** — used when registration fails its acceptance gates. Do not tune `calculate_match_confidence` weights to fix wall-scale matching problems; fix registration instead.
4. **Multi-photo routes through the single-photo pipeline.** After merging, notes carry real pixel bboxes and must flow through `classify_rectangle_roles` and the layout strategies exactly like single-photo notes. Never re-add a separate grid_position sorting path.
5. **Unmatched detail notes with valid registration are new notes**, inserted at their transformed coordinates — the overview pass misses notes on dense walls; a registered detail photo is authoritative for placement.

Registration constants (`REG_MIN_INLIERS`, `REG_MATCH_MAX_DIST_FACTOR`, etc.) live at the top of `registration.py`. Validated baseline on repo fixtures: child1/2/3 close-ups register to 24/58/82% of `leftright_wholewall.jpeg` width. If a code change moves those anchors by more than ±10%, the change is wrong.

## Debugging & Fix Philosophy

When Brad reports an output problem — wrong layout, missed note, incorrect sequencing, bad arrow routing, misidentified parallel or decision branch — the correct response is always to **fix the underlying code**: heuristics, prompts, spatial thresholds, or detection logic. Do not recommend the Review UI as the solution to an analyzer failure.

**The Review UI exists for:**
- Notes with genuinely illegible handwriting (low-res photo, bad penmanship) where no heuristic can recover the text
- Situations where the facilitator did something non-standard in the moment (ad-hoc branch, unusual note placement that intentionally deviates from the stated layout type)
- Minor final adjustments after the analyzer has already produced a substantially correct output

**The Review UI is NOT for:**
- Fixing mis-sequenced steps the heuristics should have caught
- Correcting parallels or decision branches the analyzer got wrong
- Cleaning up any systematic or repeating pattern of errors

If you find yourself about to write "the user can fix this in the Review UI," stop. Instead, identify what change to the analyzer, layout strategy, prompt, or threshold would prevent the issue from occurring. The goal is that a facilitator needs ≤2 manual edits per workflow — if they're making more than that, the code needs to improve.

When the analyzer cannot resolve ambiguity with high confidence, it should still make a best-effort decision, then flag the affected step visually in the Review UI (low-confidence highlight) so the facilitator can confirm or override. Producing no output and requiring manual reconstruction is never the right fallback.

## Commit Guidelines
- Conventional Commits format: `feat: improve arrow routing`, `fix: decision branch overlap`
- Scope commits to: analyzer, matcher, or UI changes
- Reference test case ID or requirement paragraph in commit body
- Note which commands were rerun (e.g., `python test_parallel_decision.py`)
- PRs must include before/after screenshots or PDFs from `outputs/` for any layout/PDF change
- Never commit: `.env`, `uploads/`, generated PDFs, API keys

## Security
- API key and Flask secret live in `.env` via `os.environ` — never hard-code
- `Anthropic api key.txt` in `project_docs/` is a local-only placeholder — keep private
- Scrub `uploads/` and `outputs/` before sharing logs (may contain wall photos with sensitive content)
- Filenames sanitized via `secure_filename`; uploads limited to 10MB images only