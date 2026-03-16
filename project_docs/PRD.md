# Product Requirements Document (PRD) - Sticky Note Workflow Processor
_Last updated: 2026-02-14_

## 1. Overview
**Problem**: Process workshops capture dozens of analog sticky notes that must be digitized. Manual re-entry takes hours, introduces transcription errors, and breaks the visual context (parallel swim lanes, decision diamonds, ad-hoc notes).
**Vision**: Turn 1-6 smartphone photos of a sticky-note wall into a structured, professional PDF that preserves layout semantics (parallel work, decisions, swim lanes) with minimal manual cleanup.
**Current Release Target**: Internal alpha (v0.9) that converts facilitated workshops into PDFs in under five minutes. The code already covers all four supported layouts but still stores sessions in memory and assumes trusted users.
**Success Signals**
- >=80% of readable sticky-note text captured automatically on first pass.
- <=2 manual edits per column needed before generating a PDF.
- Multi-photo workflows align detail photos with >70% confidence matches.
- Review UI exposes any transcription conflicts so nothing is silently dropped.

## 2. Core Design Constraint: Analyzer-First, UI as Last Resort

The Review UI is scoped to two situations: (1) minor final adjustments after the analyzer has produced a substantially correct output, and (2) known-hard cases where no heuristic can recover the information — illegible handwriting, non-standard in-the-moment layouts a facilitator improvised on the wall.

The Review UI is **not** the error-recovery path for analyzer failures. Every ambiguous case must result in a best-effort decision by the analyzer, not a blank or skipped step requiring manual reconstruction. The facilitator should be confirming and tweaking, not rebuilding from scratch.

When the analyzer's confidence on a step falls below a calibrated threshold (target: ~70, to be tuned against real session data), the step should be flagged visually in the Review UI — a reddish highlight on the affected note card — so the facilitator knows where to focus attention. The analyzer still commits to its best guess; the flag is a prompt for human review, not an admission of failure.

The practical standard: if a facilitator is making more than 2 manual edits per workflow column before generating a PDF, the analyzer needs to improve — not the facilitator's workflow.

## 2. Goals & KPIs
1. **Fast intake** - Upload 1 overview + N detail photos (validated with up to 5) without timeouts and keep per-photo processing under 60 seconds (`StickyNoteAnalyzer.encode_image` throttles resolution and JPEG quality).
2. **Layout fidelity** - Honor the layout radio buttons from `templates/index.html` so heuristics stay deterministic; regression tests live in `project_docs/test_cases.md`.
3. **Decision/parallel accuracy** - Flag parallel blocks when Y delta <=30 px in single/newspaper layouts and preserve reconvergence nodes in the exported PDF (driven by `ProcessMapFlowable` arrow math).
4. **Reviewer control** - Provide CRUD editing and ordering via `/save-edits/<session_id>` so facilitators can correct mistakes before export.
5. **Shareable artifact** - Export a single PDF per workflow (`/generate-pdf/<session_id>`) with note colors, shapes, labels, and branch annotations ready for executive consumption.

## 3. Personas & Top Use Cases
### Workshop Facilitator (primary)
- Needs to capture an entire wall before teardown, upload files from a laptop, and quickly confirm that parallel tracks and hand-written arrows survived.
- Uses multi-photo mode to zoom into illegible sections and relies on conflict detection before sharing results.

### Process Engineer / Analyst
- Imports the generated PDF into a report packet, so they need reliable sequencing, decision branch labels, and color-coding (headers vs body vs pain points).
- Edits metadata in Review UI to fix titles or merge duplicates without re-running AI.

### Quality Lead / Internal Ops
- Runs curated test photos (see `test_suite.py`) to verify heuristics each time Anthropic model versions change.
- Monitors conflict counts from `/detect-conflicts/<session_id>` to decide when a facilitator must re-shoot a section.

## 4. Functional Scope (as built)
### 4.1 Ingestion & Session Management
- `app.py` route `/upload` accepts multiple images, enforces extension whitelist, timestamps filenames, and stores them under session-specific prefixes inside `uploads/`.
- Layout type is captured on the form and normalized by `normalize_flow_direction`, ensuring downstream strategy lookup through `layout_strategies`.
- Each session tracks `uploaded_files`, `analysis_results`, `flow_direction`, `status`, and whether it is a multi-photo run. Session IDs are UUID8 strings stored in-memory (`sessions` dict).
- `/detect-readability/<session_id>` optionally re-analyzes the overview photo to determine if detail shots are required (>=80% readability short-circuits multi-photo processing).

### 4.2 Computer Vision Capture
- `StickyNoteAnalyzer` (in `image_analyzer.py`) resizes oversized images to <=4000 px, converts to RGB, and encodes JPEGs at quality 85 before sending to `claude-4-sonnet-20250514`.
- Prompts are split by use case:
  - `analyze_overview` forces exhaustive coverage (>=40 notes) and returns coarse `grid_position` anchors plus readability scoring.
  - `analyze_detail` focuses on text accuracy inside zoomed shots.
  - `analyze_workflow` returns pixel-precise bounding boxes, colors, shapes, and `arrows_to` targets for single-photo mode.
- Vision errors are caught and logged; truncated outputs are surfaced so facilitators know when to reshoot.

### 4.3 Workflow Layout Reasoning
- Strategies in `layout_strategies/` encapsulate heuristics for single column, newspaper columns, and horizontal/vertical swim lanes so branching logic stays isolated.
- Notes are sorted column-first (`newspaper`) or row-major depending on the selection, and `workflow_sequence` arrays back every downstream UI plus PDF behavior.
- Parallel detection uses Y proximity and column grouping. Decision detection hinges on `shape == 'diamond'` and merges branch metadata into sticky note records.
- Swim lane detection happens via `NoteMatcherSystem.detect_swim_lanes` once IDs are re-assigned after sorting.

### 4.4 Multi-photo Stitching
- `process_multi_photo_session` calls `analyze_overview`, loops through `analyze_detail` results, and runs matches through `NoteMatcherSystem`.
- `NoteMatcherSystem.calculate_match_confidence` weights color (20%), shape (20%), grid position (30%), and anchor text similarity (30%) to decide merges; leftover notes are marked as overview-only with lower confidence.
- `/detect-conflicts/<session_id>` exposes mismatched detail transcriptions so the Review UI can highlight them.

### 4.5 Review & Editing Experience
- The `/review/<session_id>` template renders every analyzed workflow, surfaces duplicates, and ships a client-side editor (JS embedded in `templates/review.html`) that can:
  - Update text, color, shape, decision branches, and parallel relationships.
  - Delete mis-detected sticky notes.
  - Reorder the `workflow_sequence`.
- `/save-edits/<session_id>` applies those mutations server-side, pruning deleted IDs from the sequence and clearing dangling references so exported PDFs can trust the edited dataset.

### 4.6 Output Generation
- `/generate-pdf/<session_id>` instantiates a `ProcessMapFlowable` (ReportLab) per workflow and writes the PDF under `outputs/` with timestamped names.
- The flowable draws true note shapes (rect, diamond, oval), centers wrapped text, tracks note coordinates for wiring arrows, and renders decision branches with diverging arrows that reconverge downstream.
- Parallel steps are placed side-by-side with spacing constants, and vertical spacing is derived from the number of workflow steps to avoid clipping.

### 4.7 Testing & Validation
- `project_docs/test_cases.md` codifies two complex regression scenarios (parallel + decision; multi-column with pain points). Test harness scripts (`test_suite.py`, `test_all_layouts.py`, `test_unit_parallel.py`, etc.) automate prompts against stored fixtures in `test_images/`.
- Developers can simulate API responses with `mock_analyzer.py` when Anthropic quota is unavailable.

## 5. Non-Functional Requirements (implemented)
- **Performance**: Images larger than 4000 px are resized before upload; per-photo API requests are serialized but wrapped in retry logic (3 tries, exponential backoff). Generating PDFs stays under roughly 5 seconds due to incremental drawing.
- **Security**: API keys are read from `.env`; filenames are sanitized via `secure_filename`; uploads are constrained to images under 10 MB.
- **Reliability**: Analyzer methods always return structured dictionaries even when the model fails, letting the Review UI show raw text. Sessions include timestamps for eventual cleanup.
- **Maintainability**: Layout strategies are pluggable so new heuristics can be added without rewriting analyzer logic; tests cover each layout type.

## 6. Out-of-Scope / Backlog
- Automatic layout detection (currently manual radio button).
- True arrow-following graph traversal (today we rely primarily on spatial heuristics).
- Persistent storage for sessions, uploads, and edits (in-memory only).
- Shared or collaborative editing plus authentication.
- Alternative exports (Visio/Lucidchart, Google Drive push).

## 7. Risks & Mitigations
- **Anthropic response truncation**: mitigated by logging `stop_reason == 'max_tokens'` and falling back to raw text; backlog item to auto-chunk large walls.
- **Readability variance**: `/detect-readability` lets facilitators know when overview quality is insufficient before investing time on detail matches.
- **Session volatility**: In-memory storage means reloads wipe data; short-term mitigation is to finish review plus export in one sitting.
- **Multi-photo drift**: Matching relies on normalized grid cells; conflicts surfaced through `/detect-conflicts` highlight when manual intervention is required.

## 8. Next Steps
1. Persist sessions/uploads in SQLite or Redis so exports survive restarts.
2. Extend pain-point association logic (currently manual) to leverage `PAIN_POINT_SHAPES.md`.
3. Layer in automated regression tests around `/generate-pdf` output to guard custom drawing logic.
4. Instrument processing time per photo and conflict counts for future KPIs.

