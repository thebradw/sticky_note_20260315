---
description: Dump raw Claude Vision response for a single test image to debug note detection
argument-hint: "<filename.jpeg> [layout]  — layout is optional; auto-detected from filename for canonical fixtures"
---

Run the diagnostic tool against a single image and print the raw analyzer output.
Layout is inferred automatically for known test images (see `_LAYOUT_DEFAULTS` in
`diagnose_detection.py`).  To override, pass it explicitly as the second argument.

```bash
python diagnose_detection.py test_images/$ARGUMENTS
```

Review the JSON output for:
- Detected note count vs expected
- `shape` values — verify standard vs non-standard (pain points)
- `center_x` / `center_y` values — check spatial layout matches photo
- `parallel_with` and `decision_branches` links — verify branch detection
- `arrows_to` lists — verify flow sequencing

If detection looks wrong, cross-reference `project_docs/REQUIREMENTS.md` for the relevant
threshold and `project_docs/test_cases.md` for the expected output for this fixture.
