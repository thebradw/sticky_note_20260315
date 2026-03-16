# Repository Guidelines

## Project Structure & Module Organization
`app.py` orchestrates uploads, session tracking, editing, and PDF rendering; `image_analyzer.py` hosts StickyNoteAnalyzer and `matcher.py` aligns photos. UI templates live in `templates/` with JS/CSS in `static/`. Analyzer fixtures sit in `test_images/`, and runtime artifacts belong in `uploads/` (raw photos) and `outputs/` (rendered PDFs). Keep reference docs (`ARCHITECTURE.md`, `REQUIREMENTS.md`, and `test_cases.md`) open whenever you adjust analyzer heuristics or layout rules.

## Build, Test, and Development Commands
- `python app.py`: start the Flask reviewer UI, then browse to `http://localhost:5000`.
- `python diagnose_detection.py test_images/<file>.jpeg`: dump the raw Claude Vision response for a single image while debugging note detection.
- `python test_parallel_decision.py` / `python test_all_layouts.py`: smoke-test flow merging, diamonds, and parallel arrows without the web tier.
- `pytest test_delete_simple.py -q` (or any `test_*.py`): target Flask endpoint regressions quickly.

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indents, snake_case functions (`analyze_workflow`), PascalCase classes (`ProcessMapFlowable`), and descriptive dict keys reflecting analyzer payloads (`parallel_with`, `decision_branches`). Prefer small helpers over long procedural blocks, keep functions pure, and guard file writes with `os.path` checks. Reuse the existing logging or print patterns in CLI scripts so diffs stay readable.

## Testing Guidelines
Use the standalone scripts for visual logic while relying on pytest for Flask routes and pure helpers. When a heuristic changes, capture the JSON diff via `diagnose_detection.py`, drop any new fixture under `test_images/`, and document the manual scenario in `test_cases.md`. Tests and scripts should assert note counts, branch links, and `workflow_sequence` ordering rather than just success logs.

## Commit & Pull Request Guidelines
Adopt Conventional Commits (for example, `feat: improve arrow routing`), and keep each commit scoped to analyzer, matcher, or UI changes. Reference the relevant test case ID or requirement paragraph in the body and note which commands you reran (`python test_parallel_decision.py`). Pull requests must summarize the user-visible impact, list updated tests, and attach before/after screenshots or PDFs from `outputs/` for layout tweaks; never include `.env`, uploads, or generated PDFs themselves.

## Security & Configuration Tips
Load Anthropic keys and Flask secrets from `.env` via `os.environ`, never hard-code credentials, and keep the provided `Anthropic api key.txt` private. Scrub `uploads/` and `outputs/` before sharing logs because they may contain sensitive wall photos; when debugging issues externally, redact sticky-note text and share only bounding boxes or anonymized captions.
