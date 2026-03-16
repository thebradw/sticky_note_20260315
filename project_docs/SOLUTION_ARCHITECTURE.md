# Solution Architecture - Sticky Note Workflow Processor
_Last updated: 2026-02-16_

## 1. Technology Stack & Runtime Environment
- **Backend**: Python 3.11+, Flask web server, ReportLab for PDF rendering, Pillow for image prep, Anthropic Claude Vision API for OCR/layout metadata, Requests for HTTP utilities, and the standard library (uuid, datetime, json, os, math).
- **Front-end**: Server-rendered Jinja templates (`templates/`) with vanilla HTML/CSS/JS; inline scripts call Flask JSON routes via `fetch`.
- **Supporting libraries**: `werkzeug` for secure filenames, `python-dotenv` for secrets, `difflib` for fuzzy string scoring, and `anthropic` SDK (Claude 4 Sonnet).
- **Tooling**: Node dependency (`esprima`) for optional JS parsing, CLI helpers for installing dependencies and running diagnostics, and regression scripts covering delete flows, analyzer accuracy, and API connectivity.
- **Runtime storage**: `uploads/` for source photos, `outputs/` for PDFs (currently empty), and an in-memory `sessions` dict for transient workflow state.

## 2. Structural Overview
### Directory Summary
| Directory | Responsibility |
| --- | --- |
| `./.claude` | Local Codex/Claude CLI harness configuration; includes `settings.local.json` specifying allowed shell commands. |
| `./layout_strategies` | Strategy objects used by the analyzer to group/sort notes for single column, newspaper, and swim-lane layouts. |
| `./node_modules` | npm-managed dependencies (only `esprima`) plus helper binaries under `.bin`. |
| `./outputs` | Destination for generated PDFs; empty at the moment but wired to `/generate-pdf`. |
| `./project_docs` | Living documentation set (requirements, reference heuristics, troubleshooting, PRD, component map, etc.). |
| `./static` | Reserved for shared CSS/JS; currently unused because templates inline their assets. |
| `./templates` | Jinja templates for upload, processing status, and the rich Review UI. |
| `./test_images` | Seven canonical JPEG fixtures covering every supported layout for regression tests. |
| `./uploads` | Local cache of pasted workflow photos from manual sessions and automated uploads; feeds analyzer tests. |
| `./__pycache__` | Python bytecode caches for core modules; safe to delete when rebuilding. |
| `./layout_strategies/__pycache__` | Bytecode caches for each strategy; regenerated automatically. |
| `./node_modules/.bin` | Windows-friendly shims for `esparse`/`esvalidate` commands shipped with esprima. |
| `./node_modules/esprima` | Vendored JavaScript parser dependency (README, ChangeLog, license, binaries, dist bundle). |

### Root-Level Files & Scripts
| Path | Purpose |
| --- | --- |
| `.env` | Environment variables (Anthropic API key, Flask secret); loaded via `python-dotenv` and excluded from version control. |
| `app.py` | Main Flask application with upload/analysis/review/pdf routes and nested `ProcessMapFlowable` renderer. |
| `clone github and launch vs code.txt` | Quickstart steps for cloning the upstream repo and opening it in VS Code. |
| `diagnose_detection.py` | CLI helper exposing `diagnose_image()` to print raw Claude output, bounding boxes, and sample note metadata for a specified file. |
| `file test01.py` | Setup sanity script that imports anthropic, Pillow, ReportLab, and os to ensure dependencies are installed. |
| `image_analyzer.py` | Implements `StickyNoteAnalyzer` for overview/detail analysis, multi-photo merging, duplicate detection, and layout-aware sorting. |
| `install anthropic into python.py` | One-liner script to `pip install anthropic pillow reportlab requests python-dotenv` using `subprocess`. |
| `localhost.txt` | Stores `http://localhost:5000` for quick copy/paste into a browser. |
| `matcher.py` | Defines `NoteMatcherSystem` for overview/detail matching, confidence scoring, swim-lane detection, and conflict handling. |
| `mock_analyzer.py` | Mock `StickyNoteAnalyzer` returning deterministic sample data so the PDF renderer can be tested offline. |
| `nul` | Legacy placeholder entry (Windows NUL device); not referenced by the app. |
| `package-lock.json` | npm lockfile pinning `esprima@4.0.1`. |
| `package.json` | npm manifest (package metadata, `esprima` dependency, placeholder `test` script). |
| `project directory path for cmd prompt.txt` | Instructions for `cd C:\Users\bradw\sticky-note-processor` and `python app.py`. |
| `test.py` | Console script verifying anthropic/Pillow/ReportLab/requests/dotenv imports and printing Python version + executable path. |
| `test_all_layouts.py` | Runs `StickyNoteAnalyzer` against representative layouts via `test_layout()` and `main()`, logging parallels + decisions. |
| `test_api.py` | Anthropic API connectivity check: iterates through preferred model names until one replies with "working!". |
| `test_delete.py` | HTTP-based smoke test that hits `/review`, posts to `/save-edits`, and verifies delete behavior for session `a06bc6fc`. |
| `test_delete_comprehensive.py` | Full end-to-end delete regression that uploads a test image, waits for analysis, edits data, and triggers PDF export. |
| `test_delete_simple.py` | Flask test-client suite featuring `create_mock_session()` and `test_delete_backend()` for backend-only delete validation. |
| `test_flask.py` | Minimal Flask server verifying that the runtime can serve HTML on localhost. |
| `test_parallel_decision.py` | Analyzer regression script centered on parallel block and decision-diamond detection via `test_analyze_workflow()`. |
| `test_suite.py` | Holds `WorkflowTestSuite` with 10 assertions (branch ordering, duplicates, parallels) and a CLI entry point. |
| `test_unit_parallel.py` | Pure-Python unit tests for `_calculate_relationships_from_coordinates` using handcrafted mock notes. |
| `trigger_upload.py` | Requests-based utility: uploads a local PNG, captures the session ID, and invokes `/process/<session_id>`. |

## 3. Backend Application (`app.py`)
- **Dependencies**: Flask core (`Flask`, `render_template`, `request`, `redirect`, `url_for`, `flash`, `jsonify`), `werkzeug.utils.secure_filename`, `uuid`, `datetime`, `os`, `json`, ReportLab (lazy import inside `/generate-pdf`), and the local `StickyNoteAnalyzer` class.
- **Session store**: `sessions` is a process-level dict keyed by an 8-character UUID, storing uploaded file metadata, analyzer results, layout choice, status, timestamps, and a `multi_photo` boolean.
- **Upload pipeline**: `/upload` validates files, normalizes layout selection via `normalize_flow_direction()`, stamps filenames with the session ID and upload time, and sets the first file as `overview`. Subsequent routes build on this session record.
### Route & Helper Functions
| Function | Description |
| --- | --- |
| `allowed_file(filename)` | Guards uploads by extension using `ALLOWED_EXTENSIONS`. |
| `normalize_flow_direction(value)` | Maps user input (and legacy aliases like `left-right`) to canonical layout strategy keys. |
| `index()` | Renders `templates/index.html` (GET `/`). |
| `upload_files()` | Handles multi-file POSTs, writes them under `uploads/`, records metadata, and redirects to `/analyze/<session_id>`. |
| `analyze(session_id)` | Renders the progress page (`templates/analysis.html`) for a given session. |
| `process_images(session_id)` | Calls `StickyNoteAnalyzer` in single-photo or multi-photo mode, populates `analysis_results`, and returns JSON for the progress UI. |
| `review(session_id)` | Ensures status is `analyzed`, logs sample notes for debugging, and renders `templates/review.html` with all analysis payloads. |
| `save_edits(session_id)` | Applies edits/deletions/order changes from the Review UI by mutating in-memory `sticky_notes` and `workflow_sequence`. |
| `detect_readability(session_id)` | Reuses `analyze_overview` to report readability stats and whether detail photos are required (>80% readable). |
| `merge_notes(session_id)` | Combines two note IDs (per reviewer input) by deleting one occurrence and updating `workflow_sequence`. |
| `add_note(session_id)` | Creates a manual note (text/color/shape) with `source="manual"` and inserts it after a provided step ID or at the end. |
| `detect_conflicts(session_id)` | Returns any recorded conflicts generated by `process_multi_photo_session` so the Review UI can highlight them. |
| `generate_pdf(session_id)` | Instantiates `ProcessMapFlowable` for each workflow or swim lane, renders notes/arrows/branches, and writes the PDF under `outputs/`. |
| `cleanup()` | Placeholder route returning `{status:"Cleanup complete"}`; hook for future temp-file purging. |

### `ProcessMapFlowable` Methods
| Method | Role |
| --- | --- |
| `__init__` | Stores notes/sequence, resets geometry caches, and computes a safe height per workflow. |
| `wrap` | ReportLab hook returning `(width, height)` used by the document layout engine. |
| `calculate_fixed_height` | Estimates required height (85 pt per step) to avoid clipping long flows. |
| `get_note_fill_color` | Translates analyzer color strings into ReportLab colors; defaults to light green when unknown. |
| `draw_note` | Renders rectangles, ovals, or diamonds plus centered wrapped text. |
| `draw_arrow` | Draws arrows with correct arrowhead orientation for horizontal and vertical movement. |
| `wrap_text` | Breaks sticky-note text into <=18-character lines for PDF readability. |
| `is_rectangle_shape` | Flags rectangles/headers for subtle layout adjustments. |
| `draw` | Master renderer: iterates `workflow_sequence`, branches into decision/parallel/pain-point handlers, and records coordinates for deferred arrows. |
| `build_decision_flows` | Analyzes `decision_branches` metadata to determine YES/NO ranges and reconvergence points. |
| `draw_decision_flow` | Positions decision diamonds, draws their YES-right/NO-down branches, and ensures reconvergence is plotted once. |
| `draw_regular_step` | Places a single-step note centered on the main column with downward arrow spacing. |
| `draw_single_note` | Reusable primitive for drawing a note at coordinates and capturing its bounding box. |
| `draw_pain_points` | Renders attached pain-point annotations (oval, small font, dashed border) beside their anchors. |
| `draw_single_pain_point` | Handles the oval drawing math and label positioning for one pain note. |
| `identify_parallel_groups` | Scans `parallel_with` relationships to build horizontal groups for side-by-side rendering. |
| `draw_parallel_group` | Places parallel notes with `PARALLEL_SPACING`, draws split arrows ahead and merge arrows below. |
| `draw_split_arrow` | Shows the main arrow splitting into multiple horizontal lanes before parallel steps. |
| `draw_merge_arrow` | Collects branch outputs and merges them back with a combined arrow tail. |
| `draw_decision_arrows` | Renders the short YES/NO labels/arrows hugging the diamond body. |
| `draw_decision_arrows_to_steps` | Routes branch arrows from diamonds to the first step in each branch (includes closures for YES/NO arrowheads). |
| `_queue_deferred_arrow` | Stores arrow metadata until both endpoints are drawn (prevents overlapping branch art). |
| `draw_deferred_decision_arrows` | Processes queued branch arrows once their targets exist. |
| `draw_deferred_rejoin_arrows` | Draws arrows from branch endpoints back to the reconverge note. |

## 4. Analysis & Matching Services
### `image_analyzer.py` (`StickyNoteAnalyzer`)
- **Purpose**: Wraps every Claude Vision interaction plus local heuristics for sorting, duplicates, and readability; feeds both the Review UI and ReportLab renderer.
- **Key dependencies**: `anthropic.Anthropic`, `PIL.Image`, `base64`, `io`, `json`, `re`, `NoteMatcherSystem` (from `matcher.py`), `layout_strategies.get_layout_strategy`, and `SequenceMatcher`.
| Method | Description |
| --- | --- |
| `__init__` | Loads `.env`, instantiates the Anthropic client, and prepares the matcher. |
| `encode_image` | Resizes overly large images (<=4000 px), converts to RGB, applies JPEG quality 85, and returns base64. |
| `analyze_overview` | Exhaustive scan of the overview photo (>=40 notes) returning color/shape/text plus grid_position and readability metrics. |
| `analyze_detail` | Focuses on text clarity for close-up photos; output feeds the matcher. |
| `process_multi_photo_session` | Combines overview + detail analyses, merges matches, tracks conflicts/unmatched notes, sorts per layout, and detects swim lanes. |
| `analyze_workflow` | Single-photo mode capturing bounding boxes, arrow hints, and derived `workflow_sequence` using the selected layout strategy. |
| `find_duplicate_notes` | Searches aggregated results for similar notes (text/color/position) so the Review UI can prompt merges. |
| `notes_similar` | Boolean helper for `find_duplicate_notes` that tolerates minor text differences. |
| `calculate_similarity` | Returns a float score for how alike two notes are (used for duplicates). |
| `_annotate_note_geometry` | Adds width/height/center based on bounding boxes for downstream math. |
| `_calculate_relationships_from_coordinates` | Derives parallels, pain points, decision branches, and adjacency purely from coordinates plus layout context. |

### `matcher.py` (`NoteMatcherSystem`)
- **Purpose**: Normalizes positions, scores overview/detail pairings, merges text confidently, exposes swim-lane groupings, and resolves conflicts for manual review.
| Method | Description |
| --- | --- |
| `__init__` | Configures a 10x10 grid for normalized coordinates. |
| `normalize_position` | Maps textual positions ("upper-middle center") to `grid_row`/`grid_col`/`grid_cell` values. |
| `calculate_match_confidence` | Weighted score combining color/shape/position/text matches. |
| `_colors_similar` | Treats related color names (e.g., yellow/cream) as similar for scoring. |
| `_shapes_similar` | Treats related shapes (square/rectangular, oval/circle, diamond/rhombus) as similar. |
| `_calculate_position_similarity` | Returns 0?1 similarity based on Euclidean distance across the normalized grid. |
| `match_detail_to_overview` | Matches detail notes to overview anchors, returning matches, unmatched lists, and conflicts. |
| `_merge_notes` | Combines overview geometry with detail text, recording `confidence` and `source` metadata. |
| `detect_swim_lanes` | Clusters notes into horizontal or vertical lanes to drive PDF sectioning. |
| `resolve_conflict` | Applies a reviewer-selected detail note to a conflict record. |

### `layout_strategies/` Files
| File | Role |
| --- | --- |
| `layout_strategies/base.py` | Defines `WorkflowLayoutStrategy` with overridable `group_workflows`/`sort_workflow`. |
| `layout_strategies/single_column.py` | Straight-down workflow ordering plus inherited shape-only pain-point detection and anchor attachment logic. |
| `layout_strategies/newspaper.py` | Column-aware sorting plus inherited shape-only pain-point detection/attachment and helper methods for anchors/column centers. |
| `layout_strategies/horizontal_swim_lanes.py` | Groups notes into lanes separated by >100 px vertically, sorts each lane left-to-right. |
| `layout_strategies/vertical_swim_lanes.py` | Groups notes into lanes separated by >150 px horizontally, sorts each lane top-to-bottom. |
| `layout_strategies/__init__.py` | Exports `WorkflowLayoutStrategy`, `LAYOUT_STRATEGIES`, and `get_layout_strategy`. |
| `layout_strategies/__pycache__/*.pyc` | Interpreter caches for the strategy modules; safe to delete. |

## 5. Front-End Templates & Static Assets
| Template | Description |
| --- | --- |
| `templates/index.html` | Upload UI with layout radio buttons, multi-file input, and plain-JS form submission to `/upload`. |
| `templates/analysis.html` | Progress dashboard listing uploaded files, animating a progress bar, and invoking `/process/<session_id>` via `fetch`. |
| `templates/review.html` | Extensive review/editor UI with drag/drop ordering, conflict highlighting, manual edits, and buttons for saving or generating PDFs. |

- `static/` currently has no files; CSS/JS live directly in the templates for now.

## 6. Utility Scripts & Test Harness
| File | Notes |
| --- | --- |
| `diagnose_detection.py` | `diagnose_image()` prints raw Claude JSON, bounding boxes, sample notes, decision flags, and image dimensions for a chosen file. |
| `install anthropic into python.py` | Runs `pip install anthropic pillow reportlab requests python-dotenv` via `subprocess.check_call`. |
| `mock_analyzer.py` | Shipping stub: `StickyNoteAnalyzer.analyze_workflow()` returns mocked notes and `find_duplicate_notes()` always returns []. |
| `trigger_upload.py` | POSTs a local PNG to `/upload`, parses the redirect session ID, and immediately calls `/process/<id>` to simulate the browser flow. |
| `test.py` | Prints whether anthropic/Pillow/ReportLab/requests/dotenv imports succeed and logs Python version + executable path. |
| `test_all_layouts.py` | `test_layout()` + `main()` iterate fixture images, run the analyzer, and display parallel + decision metadata. |
| `test_api.py` | Loads `ANTHROPIC_API_KEY` via dotenv, cycles through candidate model names, and prints the first one that responds "working!". |
| `test_delete.py` | Hits `/review` and `/save-edits` via HTTP with example payloads to confirm delete flows still work. |
| `test_delete_simple.py` | `create_mock_session()` seeds fake analyzer output; `test_delete_backend()` exercises `/save-edits` using Flask's test client. |
| `test_delete_comprehensive.py` | Uploads `uploads/04d10571_20250823_145619_IMG_2438.jpeg`, waits for analyzer completion, edits data, checks PDF generation. |
| `test_flask.py` | Tiny Flask app returning static HTML to confirm the runtime serves HTTP requests. |
| `test_parallel_decision.py` | `test_analyze_workflow()` runs the analyzer on `test_images/newspaper_1header_decision.jpeg` and prints parallel/decision info. |
| `test_suite.py` | `WorkflowTestSuite` runs 10 validation checks (decision integrity, duplicates, parallels) across seven fixture images. |
| `test_unit_parallel.py` | Crafted mock notes validate `_calculate_relationships_from_coordinates()` for different layouts and pain-point handling. |

## 7. Documentation Assets (`project_docs/`)
| File | Description |
| --- | --- |
| `project_docs/AGENTS.md` | Repo guidelines for agents (structure, commands, coding/test conventions, security reminders). |
| `project_docs/ARCHITECTURE.md` | Legacy system architecture overview (flow diagrams, deployment notes). |
| `project_docs/Anthropic api key.txt` | Plain-text placeholder storing the Anthropic key locally; never commit upstream. |
| `project_docs/BRANCH_OVERLAP_FIX-decision-yesno-position.md` | Explains the fix for overlapping YES/NO branch lists and references the updated code blocks. |
| `project_docs/COMPONENT_MAP.md` | Table mapping major components, responsibilities, dependencies, and maturity. |
| `project_docs/DECISION_FIX_SUMMARY-diamond-YESno-positioning.md` | Details the YES-right/NO-down PDF rendering change set with line references. |
| `project_docs/NEWSPAPER_LAYOUT_REFERENCE.md` | Reference guide for detecting and reading newspaper-style workflows column-by-column. |
| `project_docs/PAIN_POINT_SHAPES.md` | Defines how non-standard sticky-note shapes are interpreted/rendered as pain points. |
| `project_docs/PRD.md` | Product requirements document (vision, KPIs, personas, scope, risks). |
| `project_docs/REQUIREMENTS.md` | Foundational requirements including layout taxonomy, detection rules, edge cases, success criteria. |
| `project_docs/SOLUTION_ARCHITECTURE.md` | This document; comprehensive file/function/dependency breakdown for the current codebase. |
| `project_docs/TROUBLESHOOTING.md` | Checklist for diagnosing PDF button issues (restart Flask, clear cache, inspect logs). |
| `project_docs/USER_STORIES.md` | Persona-aligned stories (US-01..08) with acceptance criteria tied to implementation artifacts. |
| `project_docs/test_cases.md` | Detailed descriptions of canonical test flows with pass criteria. |

## 8. Configuration & Vendor Dependencies
- `.claude/settings.local.json`: JSON allow/deny list for the Codex CLI harness (permits commands like `python`, `dir`, `curl`).
- `.env`: Stores `ANTHROPIC_API_KEY`, `FLASK_SECRET_KEY`, upload/output configuration; loaded at runtime.
- `package.json` / `package-lock.json`: npm metadata locking `esprima@4.0.1`.
- `node_modules/.package-lock.json`: npm-internal metadata for nested dependencies; mirrors top-level lock info.
### `node_modules/.bin` shims
| File | Role |
| --- | --- |
| `node_modules/.bin/esparse` | Shim that invokes `../esprima/bin/esparse.js` for Unix-style shells. |
| `node_modules/.bin/esparse.cmd` | Windows CMD shim for `esparse`. |
| `node_modules/.bin/esparse.ps1` | PowerShell shim for `esparse`. |
| `node_modules/.bin/esvalidate` | Shim for `../esprima/bin/esvalidate.js`. |
| `node_modules/.bin/esvalidate.cmd` | Windows CMD shim for `esvalidate`. |
| `node_modules/.bin/esvalidate.ps1` | PowerShell shim for `esvalidate`. |

### `node_modules/esprima` contents
| File | Description |
| --- | --- |
| `node_modules/esprima/README.md` | Upstream README describing ESPrima usage. |
| `node_modules/esprima/ChangeLog` | Release notes for esprima. |
| `node_modules/esprima/LICENSE.BSD` | BSD-style license for esprima. |
| `node_modules/esprima/package.json` | esprima package metadata. |
| `node_modules/esprima/bin/esparse.js` | CLI parser entry point invoked by shims. |
| `node_modules/esprima/bin/esvalidate.js` | CLI validator entry point invoked by shims. |
| `node_modules/esprima/dist/esprima.js` | Browser-friendly bundle of esprima. |

## 9. Runtime Bytecode & Generated Files
### `__pycache__/`
| File | Origin |
| --- | --- |
| `__pycache__/app.cpython-313.pyc` | Bytecode for `app.py`. |
| `__pycache__/image_analyzer.cpython-313.pyc` | Bytecode for `image_analyzer.py`. |
| `__pycache__/matcher.cpython-313.pyc` | Bytecode for `matcher.py`. |
| `__pycache__/mock_analyzer.cpython-313.pyc` | Bytecode for `mock_analyzer.py`. |

### `layout_strategies/__pycache__/`
| File | Origin |
| --- | --- |
| `layout_strategies/__pycache__/__init__.cpython-313.pyc` | Bytecode for `layout_strategies/__init__.py`. |
| `layout_strategies/__pycache__/base.cpython-313.pyc` | Bytecode for `layout_strategies/base.py`. |
| `layout_strategies/__pycache__/horizontal_swim_lanes.cpython-313.pyc` | Bytecode for `horizontal_swim_lanes.py`. |
| `layout_strategies/__pycache__/newspaper.cpython-313.pyc` | Bytecode for `newspaper.py`. |
| `layout_strategies/__pycache__/single_column.cpython-313.pyc` | Bytecode for `single_column.py`. |
| `layout_strategies/__pycache__/vertical_swim_lanes.cpython-313.pyc` | Bytecode for `vertical_swim_lanes.py`. |

## 10. Data Assets & Fixtures
### `test_images/` fixtures
| File | Description |
| --- | --- |
| `test_images/child1_wallcloseup.jpeg` | Detail close-up of the first column (child1) used for multi-photo zoom tests. |
| `test_images/child2_wallcloseup.jpeg` | Detail close-up of the second column (child2). |
| `test_images/child3_wallcloseup.jpeg` | Detail close-up of the third column (child3). |
| `test_images/leftright_headers_swimlane_painpoint.jpeg` | Left-right workflow featuring swim lanes and pain-point annotations. |
| `test_images/leftright_wholewall.jpeg` | Full wall capture of a left-right workflow for stitching tests. |
| `test_images/newspaper_1header_decision.jpeg` | Single-column/newspaper hybrid with a header note, used for parallel + decision regression. |
| `test_images/newspaper_noheader_decision.jpeg` | Pure newspaper layout with no header, emphasizing column ordering. |

### `uploads/` stored workflow photos
Runtime session artifacts — timestamped JPEGs generated during uploads. Three categories: iPhone workshop captures (`IMG_24xx`), electrical/mechanical multi-photo sets (`elec_mech_test_workflow`), and newspaper-layout regression samples (`newspaper_1header_decision`, `newspaper_noheader_decision`). These are transient; do not treat individual filenames as stable references. Canonical test inputs live in `test_images/` instead.

### `outputs/`
- Currently empty; `/generate-pdf` will populate this directory with timestamped PDFs named `<session>_<timestamp>.pdf`.

### `static/`
- Placeholder for shared CSS/JS. All current styling/scripts live inside the templates, so this folder has no files yet.

---
This document now catalogs every file, core function, layout strategy, dependency, and data asset present in the repository so product, engineering, and QA share the same architectural view.


