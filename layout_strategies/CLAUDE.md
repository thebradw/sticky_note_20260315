# layout_strategies/ — Pluggable Layout Module

## What This Directory Does
Each file implements one layout type for grouping and sorting sticky notes before PDF rendering.
The analyzer detects which layout the photo uses; the matching strategy is then selected and called
by `image_analyzer.py`. All strategies must extend `WorkflowLayoutStrategy` from `base.py`.

## Interface Contract (do not break)

Every strategy **must** implement these two methods with these exact signatures:

```python
def group_workflows(self, notes, img_width, img_height) -> list[list[dict]]:
    """Partition flat notes list into separate workflows (one list per lane/column)."""

def sort_workflow(self, workflow_notes, img_width, img_height) -> None:
    """Sort notes in-place within a single workflow group."""
```

Every `sort_workflow` implementation **must** call `self._flag_pain_point(note)` on each note
after sorting. This is how non-standard shapes (pain points) are tagged before PDF rendering.
`_flag_pain_point` is inherited from `base.py` — do not re-implement it in subclasses.

## Class Attribute Requirements

| Attribute | Type | Purpose |
| --- | --- | --- |
| `name` | `str` | Unique identifier used by the analyzer for strategy selection |
| `standard_shapes` | `set` | Inherited — override only if the layout treats shapes differently |

## Registration
New strategies must be imported and registered in `layout_strategies/__init__.py`. If a strategy
is not registered there, the analyzer cannot select it.

## Spatial Thresholds
Use the project-level constants defined in `image_analyzer.py` (imported via the parent module),
not hardcoded magic numbers. The canonical values live in `CLAUDE.md` at the repo root and in
`project_docs/REQUIREMENTS.md`. Do not change thresholds without updating `REQUIREMENTS.md`.

## Existing Strategies

| File | Layout Type | Sort Axis |
| --- | --- | --- |
| `single_column.py` | One vertical flow | Y (top → bottom) |
| `newspaper.py` | Multi-column, left → right | Column then Y |
| `horizontal_swim_lanes.py` | Rows separated by horizontal gaps | Lane then X |
| `vertical_swim_lanes.py` | Columns separated by vertical gaps | Lane then Y |

## Adding a New Strategy
1. Create `layout_strategies/<name>.py` extending `WorkflowLayoutStrategy`
2. Set `name = '<name>'` on the class
3. Implement `group_workflows` and `sort_workflow` (call `_flag_pain_point` in the latter)
4. Register it in `__init__.py`
5. Add a fixture and scenario to `project_docs/test_cases.md`
6. Rerun `python test_all_layouts.py` before committing
