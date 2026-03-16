# System Architecture

## High-Level Flow

```
┌─────────────────┐
│   User Upload   │
│  + Layout Type  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  Image Processing           │
│  - Encode to base64         │
│  - Send to Claude Vision    │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Claude Vision Analysis     │
│  Returns: Bounding boxes    │
│  + Text + Color + Shape     │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Workflow Grouping          │
│  (Based on Layout Type)     │
│  - Single: All → 1 group    │
│  - Newspaper: All → 1 group │
│  - H-Lanes: Y-gaps → N      │
│  - V-Lanes: X-gaps → N      │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Per-Workflow Detection     │
│  FOR EACH workflow:         │
│  1. Parallel (Y ±30px)      │
│  2. Decisions (diamonds)    │
│  3. Sequence (spatial sort) │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Review UI                  │
│  - Display detected notes   │
│  - Allow manual edits       │
│  - Show conflicts           │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  PDF Generation             │
│  - ProcessMapFlowable       │
│  - Render notes/arrows      │
│  - Handle parallel/decision │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────┐
│  Download PDF   │
└─────────────────┘
```

---

## Component Breakdown

### 1. Flask Web Application (`app.py`)

**Routes**:
- `/` - Upload form with layout selection
- `/upload` - Process file uploads, create session
- `/analyze/<session_id>` - Analysis progress page
- `/process/<session_id>` - Trigger Claude API analysis
- `/review/<session_id>` - Review and edit detected notes
- `/save-edits/<session_id>` - Save user corrections
- `/generate-pdf/<session_id>` - Create visual PDF
- `/detect-conflicts/<session_id>` - Find multi-photo overlaps

**Session Management**:
```python
sessions = {
    'session_id': {
        'uploaded_files': [...],
        'analysis_results': [...],
        'flow_direction': 'single-column',
        'status': 'analyzed'
    }
}
```

**PDF Rendering**: Delegates to `ProcessMapFlowable` in `pdf_renderer.py` (extracted from `app.py`). `app.py` instantiates the flowable per workflow and writes the output PDF under `outputs/`.

---

### 1b. PDF Renderer (`pdf_renderer.py`)

Standalone ReportLab module extracted from `app.py`. Contains the full `ProcessMapFlowable` class — no Flask dependency, can be imported and tested independently.

**Key Methods**:
- `draw` — Master renderer; iterates `workflow_sequence`, dispatches to decision/parallel/regular handlers, runs deferred arrow passes at end
- `build_decision_flows` — Builds exclusive YES/NO branch step lists from `decision_branches` metadata (see Known Fixes Applied)
- `draw_decision_flow` — Positions diamond + YES-right/NO-down branches, queues rejoin arrows
- `draw_regular_step` — Single non-decision step with downward arrow spacing
- `draw_single_note` — Primitive note renderer; records geometry in `note_positions` dict for arrow routing; diamond vs. rectangle anchor logic differs
- `draw_pain_points` / `draw_single_pain_point` — Oval callouts with dashed border, placed right of anchor (falls back to left if near page edge)
- `identify_parallel_groups` / `draw_parallel_group` — Side-by-side rendering with split/merge arrows
- `draw_decision_arrows_to_steps` / `draw_deferred_decision_arrows` / `draw_deferred_rejoin_arrows` — Two-pass arrow system: immediate draw when target already positioned, deferred queue when target not yet drawn
- `_queue_deferred_arrow` — De-duplication guard before appending to deferred queue

Debug `print` statements previously present in `draw_decision_flow` and `draw_deferred_rejoin_arrows` (rejoin arrow blocks) have been removed as of 2026-02-20.

---

### 2. Image Analyzer (`image_analyzer.py`)

**Main Methods**:

**`analyze_workflow(image_path, flow_direction)`**:
- Encodes image to base64
- Sends to Claude Vision API
- Parses bounding box response
- Groups workflows by layout type
- Calculates relationships
- Returns structured JSON

**`_group_workflows_by_layout(notes, flow_direction, img_width, img_height)`**:
- Single column → all notes in one list
- Newspaper → all notes in one list (sequencing handled later)
- Horizontal swim lanes → group by Y-gaps (>100px)
- Vertical swim lanes → group by X-gaps (>150px)

**`_calculate_relationships_from_coordinates(notes, img_width, img_height)`**:
- Calculates center points from bounding boxes
- Detects parallel: Y-diff ≤ 30px, side-by-side
- Detects decision branches: spatial proximity to diamond
- Marks reciprocal relationships

**`_group_by_horizontal_lanes(notes, img_height)`**:
- Sorts by Y-coordinate
- Finds gaps >100px → lane boundaries
- Returns list of lane groups

**`_group_by_vertical_lanes(notes, img_width)`**:
- Sorts by X-coordinate
- Finds gaps >150px → lane boundaries
- Returns list of lane groups

---

### 3. Multi-Photo Matcher (`matcher.py`)

**Purpose**: Link detail photos back to overview photo positions

**Main Methods**:

**`match_detail_to_overview(overview_notes, detail_notes)`**:
- Compares notes from overview vs. detail photos
- Calculates match confidence (color, shape, position, text)
- Returns matches, conflicts, unmatched

**`detect_swim_lanes(notes)`**:
- Identifies rectangular headers
- Groups notes by row ranges
- Returns swim lane structure

**Matching Confidence Factors**:
- Color match: 20 points
- Shape match: 20 points
- Position similarity: 30 points
- Text similarity: 30 points

---

## Data Structures

### Sticky Note Object
```json
{
    "id": 1,
    "text": "Sales PO",
    "color": "yellow",
    "shape": "square",
    "bbox": [100, 50, 250, 150],
    "center_x": 175,
    "center_y": 100,
    "width": 150,
    "height": 100,
    "parallel_with": 2,
    "decision_branches": {
        "yes_next_step": 10,
        "no_next_step": 11,
        "rejoin_step": 12,
        "yes_label": "Yes",
        "no_label": "No"
    },
    "confidence": 95,
    "source": "overview"
}
```

### Analysis Result
```json
{
    "summary": "Workflow description",
    "sticky_notes": [...],
    "workflow_sequence": [1, 2, 3, 4, 5],
    "workflows": [
        {
            "workflow_id": 1,
            "note_count": 5,
            "note_ids": [1, 2, 3, 4, 5]
        }
    ],
    "flow_direction": "single-column",
    "image_width": 1920,
    "image_height": 1080
}
```

---

## Detection Algorithms

### Parallel Detection

```python
def detect_parallel(note1, note2):
    # Calculate Y-coordinate difference
    y_diff = abs(note1['center_y'] - note2['center_y'])
    
    # Check if within tolerance
    if y_diff <= 30:
        # Check if side-by-side (not overlapping)
        x_gap = abs(note1['center_x'] - note2['center_x'])
        if x_gap > 50:  # Not the same note
            return True
    
    return False
```

### Decision Branch Detection

```python
def detect_decision_branches(diamond_note, all_notes):
    diamond_x = diamond_note['center_x']
    diamond_y = diamond_note['center_y']
    
    yes_candidate = None
    no_candidate = None
    
    for other_note in all_notes:
        # Check for YES branch (to the right)
        if other_note['center_x'] > diamond_x + 50:
            if abs(other_note['center_y'] - diamond_y) < 150:
                # This could be the yes branch
                distance = calculate_distance(diamond_note, other_note)
                if distance < best_yes_distance:
                    yes_candidate = other_note
        
        # Check for NO branch (below)
        if other_note['center_y'] > diamond_y + 50:
            if abs(other_note['center_x'] - diamond_x) < 200:
                # This could be the no branch
                distance = calculate_distance(diamond_note, other_note)
                if distance < best_no_distance:
                    no_candidate = other_note
    
    return yes_candidate, no_candidate
```

### Workflow Grouping (Horizontal Lanes)

```python
def group_by_horizontal_lanes(notes):
    sorted_notes = sorted(notes, key=lambda n: n['center_y'])
    
    lanes = []
    current_lane = [sorted_notes[0]]
    
    for i in range(1, len(sorted_notes)):
        y_gap = sorted_notes[i]['center_y'] - sorted_notes[i-1]['center_y']
        
        if y_gap > 100:  # New lane
            lanes.append(current_lane)
            current_lane = [sorted_notes[i]]
        else:  # Same lane
            current_lane.append(sorted_notes[i])
    
    lanes.append(current_lane)
    return lanes
```

---

## Configuration & Tuning Parameters

### Spatial Thresholds
```python
PARALLEL_Y_TOLERANCE = 30        # pixels - Y-diff for parallel detection
LANE_GAP_HORIZONTAL = 100        # pixels - gap between horizontal lanes
LANE_GAP_VERTICAL = 150          # pixels - gap between vertical lanes
DECISION_YES_MIN_X = 50          # pixels - min distance right for Yes branch
DECISION_YES_MAX_Y = 150         # pixels - max Y-diff for Yes branch
DECISION_NO_MIN_Y = 50           # pixels - min distance down for No branch
DECISION_NO_MAX_X = 200          # pixels - max X-diff for No branch
```

### API Parameters
```python
CLAUDE_MODEL = "claude-4-sonnet-20250514"
MAX_TOKENS = 4000                # Higher for complex images
IMAGE_MAX_DIMENSION = 4000       # Resize if larger
IMAGE_QUALITY = 85               # JPEG quality after resize
```

### PDF Rendering
```python
NOTE_WIDTH = 120                 # Default note width (points)
NOTE_HEIGHT = 60                 # Default note height (points)
ARROW_LENGTH = 25                # Vertical spacing for arrows
DECISION_BRANCH_SPACING = 200   # Horizontal offset for branches
PARALLEL_SPACING = 160           # Horizontal spacing between parallel notes
```

---

## Error Handling

### Vision API Failures
- Retry logic: 3 attempts with exponential backoff
- Fallback: Return raw text if JSON parsing fails
- Timeout: 30 seconds per request

### Coordinate Validation
- Bounding boxes must be within image dimensions
- Center points calculated from bbox
- Invalid coordinates → skip note with warning

### Workflow Grouping Edge Cases
- Empty groups → skip
- Single note in group → treat as workflow
- Overlapping groups → use first assignment

---

## Performance Optimization

### Image Processing
- Resize large images before upload (max 4000px)
- Use JPEG compression (85% quality)
- Base64 encoding only when needed

### API Efficiency
- Batch multiple photos when possible
- Cache results in session storage
- Avoid redundant API calls

### PDF Generation
- Calculate page height dynamically
- Use custom pagesize for long workflows
- Render incrementally (don't hold entire PDF in memory)

---

## Security Considerations

### API Key Protection
- Store in .env file (never commit)
- Use environment variables in production
- Rotate keys periodically

### File Upload Validation
- Check file extensions (whitelist only)
- Limit file size (max 10MB per image)
- Sanitize filenames (use secure_filename)

### Session Management
- Generate random session IDs (UUID)
- Clean up old sessions (>24 hours)
- Don't store sensitive data in sessions

---

## Deployment Architecture

### Local Development
```
Python 3.9+
Flask (dev server)
Claude API
Local file storage
```

### Production (Render/Railway)
```
Docker container
Gunicorn WSGI server
Cloud file storage (S3/GCS)
PostgreSQL (for sessions)
Redis (for caching)
```

### Environment Variables
```
ANTHROPIC_API_KEY=sk-ant-...
FLASK_SECRET_KEY=random-key
UPLOAD_FOLDER=/tmp/uploads
OUTPUT_FOLDER=/tmp/outputs
MAX_UPLOAD_SIZE=10485760
SESSION_TIMEOUT=86400
```

---

## Future Enhancements

### Test Harness Scripts (updated)

In addition to the scripts listed in `SOLUTION_ARCHITECTURE.md`, the following were added after that doc was last updated:

- `test_pain_point_rendering.py` — unittest module importing `ProcessMapFlowable` from `pdf_renderer.py` directly. Two test cases: (1) pain point renders to the right of its anchor when horizontal space is available; (2) pain point correctly moves to the left of its anchor when placed near the right page edge. Uses a real ReportLab canvas backed by `io.BytesIO` — no mocking. Run with `pytest test_pain_point_rendering.py -q`.

---

### Arrow Detection Improvements
- Use computer vision to extract arrow paths
- Follow arrows instead of spatial heuristics
- Handle curved and angled arrows

### Auto Layout Detection
- Analyze image to determine layout type
- Remove user selection requirement
- Use clustering algorithms

### Collaborative Features
- Multiple users editing same workflow
- Real-time updates via WebSockets
- Version history and rollback

### Integration APIs
- Export to Visio XML format
- Import from Lucidchart
- Sync with Miro/Mural boards

---

---

## Known Fixes Applied

These are production bugs that have been resolved. Line references are omitted intentionally — they drift as the code evolves. If a regression appears, search `app.py` for the relevant function names.

### Diamond Geometry Tracking (`draw_single_note`)
Diamond shapes now track actual tip positions (top/bottom/left/right points) instead of bounding box edges. This enables accurate arrow routing from the correct attachment point on each diamond side. Rectangles continue to use bounding box edges.

### YES/NO Branch Direction (`draw_decision_flow`, `draw_decision_arrows`)
Standard flowchart convention is enforced: YES branches go **right** (horizontal), NO branches go **down** (continues main flow). The original code had these reversed. All three arrow-drawing functions (`draw_decision_arrows`, `draw_decision_arrows_to_steps`, `draw_deferred_decision_arrows`) were updated consistently.

### Branch Overlap Fix (`build_decision_flows`)
YES and NO branch step lists are now mutually exclusive. Previously, slice notation caused the rejoin step to appear in both branch lists, resulting in the NO branch rendering in the wrong column. The fix: YES branch stops before the NO branch start index; NO branch runs from NO start to rejoin.

```
# Correct exclusive slicing
yes_branch = sequence[yes_index:no_index]       # stops before NO start
no_branch  = sequence[no_index:rejoin_index]    # NO only, no overlap
```

Last Updated: 2026-02-20
