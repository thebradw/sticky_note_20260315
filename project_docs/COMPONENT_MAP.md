# Component Map - Sticky Note Workflow Processor
_Last updated: 2026-02-14_

| Component | Location | Responsibilities | Interfaces / Dependencies | Maturity |
| --- | --- | --- | --- | --- |
| Web & Session Layer | `app.py` routes `/`, `/upload`, `/process`, `/review`, `/save-edits`, `/detect-conflicts`, `/generate-pdf`, `/detect-readability`. | Handles HTTP requests, session state, and orchestration between analyzer, matcher, and renderer. | Flask, StickyNoteAnalyzer, ReportLab. | Alpha (complete flow, needs persistence) |
| Upload & File Store | `uploads/`, `outputs/`, helper logic in `app.py`. | Persist raw images and generated PDFs with timestamped names; enforce allowed extensions. | OS filesystem, `secure_filename`. | Alpha |
| StickyNoteAnalyzer | `image_analyzer.py`. | Encode/resize images, call Claude Vision, parse JSON, compute readability, orchestrate multi-photo runs. | Anthropic SDK, Pillow, layout strategies, NoteMatcherSystem. | Alpha with retries |
| Layout Strategy Layer | `layout_strategies/*.py`. | Provide grouping and ordering heuristics for single-column, newspaper, horizontal lanes, vertical lanes. | Consumed by StickyNoteAnalyzer and PDF renderer. | Beta (pluggable) |
| Note Matching & Lane Detection | `matcher.py`. | Normalize positions, calculate match confidence, detect swim lanes, emit conflicts. | Consumes analyzer output; informs review UI and PDF. | Alpha |
| Review UI | `templates/review.html` plus inline JS. | Display analyzer results, show conflicts, allow edits/deletions/reordering, call `/save-edits`. | Fetches JSON from Flask endpoints. | Alpha (manual QA) |
| PDF Renderer | `ProcessMapFlowable` inside `app.py`. | Draw sticky notes, arrows, decision branches, and parallel flows into a PDF. | ReportLab, edited note data from sessions. | Beta (visually validated) |
| Test Harness & Fixtures | `test_suite.py`, `test_all_layouts.py`, `test_unit_parallel.py`, `test_images/`, `mock_analyzer.py`. | Provide regression checks for layout detection, analyzer prompts, and PDF handling without hitting live APIs. | Python CLI/unittest, local fixtures. | Beta |
| Documentation | `project_docs/*.md`. | Requirements, architecture, troubleshooting, PRD, user stories, component maps, etc. | References code modules and tests. | Living docs |

