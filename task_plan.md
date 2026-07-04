# Task Plan - Final Build for Sticky Note Workflow Processor
_Last updated: 2026-07-03_

> **STATUS: BACKLOG / NOT YET IMPLEMENTED**
> This document describes planned future work, not the current state of the codebase.
> Do not treat pseudo-code or task descriptions here as existing functionality.
> Completed features are tracked in `PRD.md` (Section 4 - Functional Scope) and `REQUIREMENTS.md` (Success Criteria).
> This backlog should ideally be migrated to GitHub Issues for active tracking.

## Goal
Deliver a production-ready workflow digitization tool that ingests one or multiple sticky-note wall photos, preserves layout semantics (parallel steps, decisions, swim lanes, pain points), and outputs an accurate PDF artifact with minimal manual cleanup. Plan aligns with `project_docs/PRD.md`, `REQUIREMENTS.md`, `USER_STORIES.md`, and `SOLUTION_ARCHITECTURE.md`.

## Key Dependencies & Touchpoints
- **Flask app (`app.py`)**: upload, session mgmt, review, PDF rendering, REST helpers.
- **Analyzer stack (`image_analyzer.py`, `layout_strategies/*`, `matcher.py`)**: Claude Vision prompts, layout heuristics, multi-photo stitching.
- **Front-end templates (`templates/*.html`) + JS**: Upload UX, progress, review/editor controls.
- **Assets/data**: `uploads/`, `test_images/`, `outputs/` directories.
- **Docs/tests**: `project_docs/*`, test scripts under repo root.
- **External services**: Anthropic Claude Vision (API quotas, model IDs), ReportLab, Pillow, Requests.

## Workstreams & Tasks
### 1. Harden Ingestion & Session Persistence
**Objective**: Ensure multi-photo uploads and long-running sessions survive restarts and support background processing.
- **T1.1 Persist sessions/uploads**
  - Introduce SQLite/Redis-backed session store instead of in-memory `sessions` dict.
  - Update helpers (`upload_files`, `process_images`, `review`, etc.) to read/write through repository class.
  - Migration tasks: create ORM/dataclass mapping for `Session`, `UploadedFile`, `AnalysisResult`.
  - Dependencies: `app.py`, potential new module `storage/session_store.py`.
  - Pseudo-code:
    ```python
    # storage/session_store.py
    class SessionStore:
        def create_session(self, flow_direction, multi_photo): ...
        def add_file(self, session_id, file_meta): ...
        def update_analysis(self, session_id, analysis_payload): ...
    
    # app.py
    session_store = SessionStore(db_url=os.getenv('DATABASE_URL'))
    session_id = session_store.create_session(flow_direction, multi_photo)
    session_store.add_file(session_id, UploadedFile(...))
    ```
- **T1.2 Async/background processing option**
  - Evaluate simple job queue (RQ/Celery) or threaded worker to avoid blocking HTTP `/process/<id>`.
  - Provide polling endpoint to fetch job status.
  - Ensure job metadata stored in session store.
- **T1.3 Upload validation & limits**
  - Enforce max photo count (e.g., 6) and size (10MB) at Flask level.
  - Provide user feedback on rejection reasons via flash messages.

### 2. Analyzer Accuracy & Multi-Photo Reliability
**Objective**: Achieve KPI of >=80% readable notes captured, strong multi-photo merging.
- **T2.1 Prompt/version management**
  - Externalize prompts to `project_docs/` or `prompts/` with version tags.
  - Add config for Anthropic model fallback order (see `test_api.py`).
- **T2.2 Geometric registration for multi-photo stitching (SUPERSEDED matching-tuning task — see `IMPL_BRIEF_T4_REGISTRATION.md`)**
  - New `registration.py`: SIFT + RANSAC homography maps each detail photo into overview pixel space; validated 2026-07-02 on wall fixtures (child1/2/3 register at 24/58/82% of overview width).
  - `analyze_overview` returns pixel bboxes (same schema as `analyze_workflow`); text becomes best-effort payload, never a matching signal.
  - `matcher.match_by_geometry` assigns notes nearest-neighbor in overview space; legacy `calculate_match_confidence` retained as fallback only — do not tune its weights.
  - Multi-photo merged notes route through `classify_rectangle_roles` + layout strategies (removes the grid_position sorting bypass).
  - Arrow-follow overrides and Review UI surfacing of unmatched notes: moved to backlog, separate tasks.
- **T2.3 Auto layout detection (optional stretch)**
  - Add analyzer pass to auto-suggest layout type; still allow manual override.
  - Expose in UI as recommendation.
- **T2.4 Error handling/logging**
  - Standardize structured logs for API failures (include session_id, file name, prompt type).
  - Provide fallback to `mock_analyzer` when API unavailable.
- **Pseudo-code**:
  ```python
  def process_multi_photo_session(...):
      overview = self.analyze_overview(...)
      details = [self.analyze_detail(p) for p in detail_paths]
      matches = self.matcher.match_detail_to_overview(overview_notes, detail_notes)
      for match in matches:
          if arrow_override_applicable(match):
              apply_arrow_priority(match)
      return build_analysis_payload(...)
  ```

### 3. Layout Strategy & Heuristic Enhancements
**Objective**: Guarantee accurate sequencing for all layout types and pain-point handling.

- **T3.0 Rectangle Role Classifier (SHIPPED 2026-03 — see `IMPL_BRIEF_T3.md`; spec below kept as historical reference)**
  - Implement before workflow grouping in `image_analyzer.py`. Runs on the full note pool for every layout type.
  - **Tier 1 — Banner**: shape is `rectangle`/`rectangular`, size ≥ 1.5× median note size, Y within top 20% of image, center_x not clearly owned by one column group. Extract as `process_title` session metadata; remove from note pool before grouping.
  - **Tier 2 — Lane Header**: shape is `rectangle`, `rectangular`, or `square`, first note in the flow direction of its group after a provisional grouping pass (highest Y for vertical lanes; lowest X for horizontal lanes), size within normal range, color differs from the modal color of remaining notes in that group. Store as `lane_label` on the workflow group; remove from sequencing.
  - **Tier 3 — Process Step**: anything not matching Tier 1 or 2. Sequence normally.
  - **Edge cases**:
    - Single note in column → Tier 3 (no color comparison possible)
    - Top note same color as modal → Tier 3 (user error; facilitator corrects label in Review UI — legitimate UI use case)
  - Extend `is_rectangle_shape()` in `pdf_renderer.py` to include `'square'` so header rendering catches all rectangular note types.
  - **PDF output**: Render `process_title` as a bold heading above all lanes. Render each `lane_label` as a column/row heading above its workflow group.
  - **Dependencies**: `image_analyzer.py` (pre-pass logic), layout strategy `group_workflows` methods (receive pre-cleaned note pool), `pdf_renderer.py` (`is_rectangle_shape` fix + title/label rendering), `project_docs/REQUIREMENTS.md` (Rectangle Role Classification section).
  - **Tests**: Add fixture with banner + two labeled lanes to `test_images/`. Assert `process_title` extracted, lane labels not in `workflow_sequence`, process steps sequenced correctly. Document scenario in `project_docs/test_cases.md`.

- **T3.1 Parameterize thresholds**
  - Expose `lane_gap_threshold`, `PARALLEL_SPACING`, Y delta thresholds in config for tuning per test cases.
- **T3.2 Pain-point association**
  - Extend `NewspaperColumnsStrategy._attach_pain_points` to consider text proximity and arrow hints (see `PAIN_POINT_SHAPES.md`).
- **T3.3 Decision branch reconvergence**
  - Validate `build_decision_flows` across multi-branch diamonds; ensure `yes_branch` and `no_branch` arrays exclusive.
  - Add unit tests referencing `BRANCH_OVERLAP_FIX` and `DECISION_FIX_SUMMARY` docs.
- **Pseudo-code snippet**:
  ```python
  def build_decision_flows(notes_dict):
      flows = {}
      for diamond in filter(lambda n: n['shape']=='diamond', notes_dict.values()):
          yes_id = diamond['decision_branches'].get('yes_next_step')
          no_id = diamond['decision_branches'].get('no_next_step')
          flows[diamond['id']] = DecisionFlow(
              yes_path=_collect_branch(yes_id, stop_before=no_id),
              no_path=_collect_branch(no_id, stop_before=rejoin_id),
              rejoin=rejoin_id)
      return flows
  ```

### 3b. Low-Confidence Step Flagging (SHIPPED 2026-07-03 — see implementation note; spec below kept as historical reference)
**Objective**: Make analyzer uncertainty visible without requiring manual reconstruction — the analyzer always commits to a decision; the flag is a prompt for facilitator confirmation only.

**Implementation note (2026-07-03)**: `templates/review.html` has a `.low-confidence` CSS class with conditional rendering off `note.low_confidence`, now a reddish tint (`#dc3545` border / `#fdf0f0` background, `#f8d7da`/`#842029`/`#dc3545` badge) with a generalized "Analyzer confidence below threshold — please verify" tooltip per T3b.3. The backend sets `low_confidence` from TWO orthogonal signals: `_flag_low_confidence_text` (text-hallucination heuristic) AND `_flag_low_confidence_score`, which flags any note whose `confidence` falls below the `LOW_CONFIDENCE_THRESHOLD = 70` module constant (T3b.2). Confidence is populated on every returned note (T3b.1): the multi-photo path scores via the matcher/registration path, and `_apply_layout_pipeline` backfills single-photo notes — which Vision returns without a confidence field — to a neutral-high default of 85 (above threshold, so it does not false-flag a clean transcription; the text heuristic still catches suspect ones). The numeric pass runs after merge/dedup, sets only the boolean flag (never the confidence value), and is now functional in both single- and multi-photo sessions.
- **T3b.1 Ensure confidence field is reliably populated in single-photo mode**
  - Currently `confidence` is consistently populated in multi-photo matching (`calculate_match_confidence`). Audit `analyze_workflow` to confirm every returned note has a `confidence` value; backfill with a default (e.g., 85) where the Claude Vision response doesn't include one.
- **T3b.2 Define and expose confidence threshold as config constant**
  - Add `LOW_CONFIDENCE_THRESHOLD = 70` to app config (alongside spatial constants). Start at 70; tune after running against real session data via `diagnose_detection.py`.
  - Notes below threshold should carry a `low_confidence: true` flag in the session payload.
- **T3b.3 Render reddish highlight in Review UI for flagged steps**
  - In `templates/review.html`, add a CSS class (e.g., `.note-low-confidence`) with a reddish border/background tint on the note card.
  - Apply the class conditionally when `note.low_confidence === true` in the JS rendering loop.
  - Include a legend or tooltip ("Analyzer confidence below threshold — please verify") so facilitators understand the flag.
- **Dependencies**: `image_analyzer.py` (confidence population), `app.py` session payload, `templates/review.html` JS/CSS.

### 4. Review UI & Conflict Resolution
**Objective**: Give facilitators complete control with clear visibility into conflicts.
- **T4.1 Conflict panel**
  - Surface `analysis.conflicts` in `templates/review.html` with accept/reject UI calling `/resolve-conflict`.
- **T4.2 Manual note creation improvements**
  - Allow drag-to-position, color pickers, and shape selection consistent with analyzer output.
- **T4.3 Autosave & collaborative readiness**
  - Autosave edits via debounced API calls to reduce data loss.
  - (Stretch) Add per-session passcode or auth hook.
- **Dependencies**: `review.html` JS, `/save-edits`, new route `/resolve-conflict` invoking `NoteMatcherSystem.resolve_conflict`.
- **Pseudo-code**:
  ```javascript
  async function resolveConflict(conflictId, detailNoteId) {
      await fetch(`/resolve-conflict/${sessionId}`, {
          method: 'POST', body: JSON.stringify({ conflictId, detailNoteId })
      })
  }
  ```

### 5. PDF Rendering & Export Options
**Objective**: Produce professional-grade PDFs matching physical layouts.
- **T5.1 Pagination & scaling**
  - Add logic to paginate when `required_height` exceeds threshold; support multi-page flows.
- **T5.2 Legend & metadata**
  - Optionally include table of contents, legend for colors/shapes, and session metadata (upload date, layout type).
- **T5.3 Alternate exports** (future): JSON, CSV, Visio.
- **Dependencies**: `ProcessMapFlowable`, `/generate-pdf`, ReportLab assets.
- **Pseudo-code**:
  ```python
  page = canvas.Canvas(...)
  for section in workflows:
      flowable = ProcessMapFlowable(...)
      if cursor - flowable.height < margin:
          page.showPage(); cursor = new_page_height - margin
      flowable.drawOn(page, x=0, y=cursor-flowable.height)
      cursor -= flowable.height + spacing
  ```

### 6. Deployment & DevOps Readiness
**Objective**: Make the app easy to deploy (Render/Railway) with environment parity.
- Dockerize app with Gunicorn entrypoint; configure persistent storage for uploads/outputs.
- Provide `.env.example`, migration scripts, and README deployment steps (tie-ins to `project_docs/ARCHITECTURE.md`).
- Add health-check route and logging config.

### 7. Comprehensive Testing Strategy
**Unit Tests**
- Analyzer helpers: `_annotate_note_geometry`, `_calculate_relationships_from_coordinates`, layout strategy methods.
- Matcher scoring: color/shape/position weighting, `resolve_conflict`.
- Session store adapters (mock DB).

**Functional Tests**
- Flask route tests for `/upload`, `/process`, `/review`, `/save-edits`, `/generate-pdf` using Flask test client + mock analyzer.
- Review UI autosave + conflict resolution via Selenium-lite (headless browser) or Playwright snapshots.

**Integration Tests**
- End-to-end analyzer with real Anthropic responses using `test_images/` (flag as slow, require API key).
- PDF rendering diff tests: compare output PDF metadata or convert to images for pixel diff.
- Database-backed session lifecycle (create → process → edit → export).

**E2E Tests**
- Scripted flow: upload overview+detail set, wait for background job, review conflicts, edit note, generate PDF, verify file saved under `outputs/`.
- Multi-layout scenario: run `test_suite.py` plus manual scenario for swim lanes with pain points.
- Deployment smoke: containerized app responding to `/healthz`, `/` client interactions.

Testing harness updates:
- Expand `test_suite.py` to assert persistence outcomes and PDF existence.
- Add `pytest` config with markers (`unit`, `integration`, `anthropic`).
- Integrate CI pipeline (GitHub Actions) to run unit/functional tests on push; gate integration/E2E to nightly or manual due to API costs.

### 8. Documentation & Change Management
- Update `project_docs/PRD.md`, `REQUIREMENTS.md`, `SOLUTION_ARCHITECTURE.md`, and `COMPONENT_MAP.md` after major feature merges.
- Maintain changelog referencing task IDs; include pseudo-code snippets and configuration notes for future maintainers.
- Provide runbooks for quota exhaustion, deployment rollback, and data cleanup.

## Execution Notes
- Prioritize persistence (T1) and analyzer reliability (T2/T3) before UI polish (T4) or extra exports (T5.3).
- Each workstream should produce interim demos/PDFs for facilitator feedback.
- Attach test evidence (unit logs, PDF samples) to each pull request to avoid regression risk.
