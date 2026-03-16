---
description: Run smoke tests for flow merging, decision diamonds, and parallel arrows (no web tier required)
---

Run both smoke-test scripts in sequence. These test layout logic and PDF flow without starting Flask.

```bash
python test_parallel_decision.py && python test_all_layouts.py
```

These tests cover:
- Parallel note detection and merging (`test_parallel_decision.py`)
- All four layout types: single column, newspaper, horizontal swim lanes, vertical swim lanes (`test_all_layouts.py`)

Run these after any change to `image_analyzer.py`, `layout_strategies/`, or `pdf_renderer.py`.
Check output for note counts, branch links, and `workflow_sequence` ordering — not just "success" logs.
