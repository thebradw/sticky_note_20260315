---
description: Run Flask endpoint regression tests via pytest
---

Run the canonical pytest suite for Flask route and pure-helper regressions.

```bash
pytest test_delete_simple.py test_pain_point_rendering.py -q
```

These are the two active regression suites. `test_delete_simple.py` covers session/delete
endpoint behavior. `test_pain_point_rendering.py` covers pain point shape detection and PDF
rendering of non-standard shapes.

The following test files exist but are **not canonical** — do not run or rely on them:
- `test_delete.py` — superseded by `test_delete_simple.py`
- `test_delete_comprehensive.py` — exploratory, not maintained
- `test.py` — scratch file

Run this after any change to Flask routes in `app.py` or shape-handling logic in `pdf_renderer.py`.
