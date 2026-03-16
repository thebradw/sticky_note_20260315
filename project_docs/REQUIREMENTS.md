# Sticky Note Workflow Analyzer - Requirements

## Vision
Transform physical sticky note workflows from business process mapping sessions into digital, professional PDF process maps. The tool must handle real-world complexity: multiple photos spanning entire walls, various workflow layouts, parallel steps, decision branches, and swim lanes.

## Core Capabilities

### 1. Image Analysis
- Extract text from sticky notes using Claude Vision API
- Identify note attributes: color, shape, position (bounding box coordinates)
- Detect hand-drawn arrows showing flow between steps
- Handle overlapping photos and photo stitching for wall-spanning workflows

### 2. Workflow Structure Detection
- **Parallel Steps**: Notes that execute simultaneously (side-by-side at same vertical level)
- **Decision Diamonds**: Diamond-shaped notes with Yes/No branches that reconverge
- **Swim Lanes**: Multiple independent workflows in the same image
- **Sequential Flow**: Standard step-by-step progression

### 3. Output Generation
- Professional PDF with realistic sticky note visualization
- Arrows showing flow between steps
- Proper rendering of parallel steps (side-by-side)
- Decision branches with labeled paths (Yes/No)
- Support for multi-page workflows

---

## Layout Taxonomy

### Type 1: Single Column (Straight Down)
**Description**: One vertical workflow with possible parallel steps and decision branches

**Characteristics**:
- Notes flow top-to-bottom in single column
- Parallel steps appear side-by-side at same Y-coordinate
- Decision diamonds create branches that rejoin later
- Most common for simple linear processes

**Detection Rules**:
- Notes within Y ±30px = **PARALLEL** (if side-by-side)
- Diamond shapes trigger decision branch detection
- Sequence: Top → Bottom

**Example Use Cases**:
- Manufacturing process flow
- Single department approval workflow
- Linear project phases

---

### Type 2: Newspaper Columns (Sequential Columns)
**Description**: Single workflow split across multiple columns - read down then right

**Characteristics**:
- One continuous workflow spanning multiple columns
- Read DOWN column 1 completely, then DOWN column 2, etc.
- Notes at same Y-level in different columns are **NOT parallel** (sequential)
- Parallel steps can still exist WITHIN a column

**Detection Rules**:
- Group into columns by X-coordinate gaps (>150px)
- Sort each column top→bottom
- Sequence: Column 1 (all), Column 2 (all), Column 3 (all)
- Parallel detection: Only within same column, Y ±30px

**Example Use Cases**:
- Long processes that don't fit in one column
- Wall-spanning workflows captured in single photo
- Complex multi-step operations

**Critical**: Do NOT mark notes as parallel just because they're at same Y-level - they must be in the SAME column.

---

### Type 3: Horizontal Swim Lanes
**Description**: Multiple horizontal workflows stacked vertically - each row is independent

**Characteristics**:
- Multiple distinct workflows in same image
- Each row represents different process/department
- Often labeled with department names
- Flow is left-to-right within each row

**Detection Rules**:
- Group by Y-coordinate gaps (>100px between rows)
- Each row becomes separate workflow
- Within row: sequence left→right
- Parallel detection: Within same row only

**Example Use Cases**:
- Cross-functional process maps (Sales row, Engineering row, Manufacturing row)
- Multiple product lines shown together
- Comparative workflows (Current State vs Future State)

**Output**: Multiple independent PDFs or separate sections in one PDF

---

### Type 4: Vertical Swim Lanes (Multiple Columns)
**Description**: Side-by-side vertical workflows in separate columns - each column is independent

**Characteristics**:
- Multiple distinct workflows in same image
- Each column represents different process/department
- Often labeled with column headers
- Flow is top-to-bottom within each column

**Detection Rules**:
- Group by X-coordinate gaps (>150px between columns)
- Each column becomes separate workflow
- Within column: sequence top→bottom
- Parallel detection: Within same column only

**Example Use Cases**:
- Department-specific processes shown together
- Regional variations of same process
- Different product workflows

**Output**: Multiple independent PDFs or separate sections in one PDF

---

## Rectangle Role Classification

Rectangular notes serve as semantic labels, not process steps. This classification must run as a **pre-processing pass before workflow grouping**, so that Tier 1 and Tier 2 notes are excluded from sequencing entirely. Color of sticky notes is arbitrary, do not use color to identify shape pattern. Color is only to be recorded for output. 

### Tier 1 — Process Banner (exclude from sequencing; use as PDF title)
A banner is always a larger rectangle — notably wider and/or taller than the standard sticky notes in the same photo. Facilitators use these consistently to name a department or describe the overall workflow being mapped. They appear at the top of the image, typically centered above all columns.

**Detection criteria (all must be true):**
- Shape: rectangle or rectangular (Claude Vision classification)
- Size: width OR height is ≥ 1.5× the median note size in the photo
- Y-position: within the top 20% of the image
- Position: center_x is not clearly owned by a single column group (falls in a gap, or spans multiple groups)

**Output**: Extracted as `process_title` metadata on the session. Rendered as a heading above all lanes in the PDF. Not assigned to any workflow sequence.

### Tier 2 — Lane Header (exclude from sequencing; use as lane label)
A standard-sized rectangle (square or rectangular) at the entry point of a specific column or row group whose color differs from the process steps in that group. Labels the lane — e.g., "Capital", "Inventory", "Sales", "Engineering". Facilitators consistently use a distinct color for lane headers to visually separate them from process steps.

**Detection criteria (all must be true):**
- Shape: rectangle, rectangular, or square
- Position: **first note in the flow direction** of its assigned group after grouping:
  - Vertical swim lanes & single column: highest Y (topmost note in the column)
  - Horizontal swim lanes: lowest X (leftmost note in the row)
- Size: within normal note size range (not a banner)
- Color: **different from the modal color** of the remaining notes in the same group (modal = most frequently occurring color among the non-candidate notes in that group)

**Edge cases:**
- **Single note in group**: Only one note exists — no color comparison possible. Treat as Tier 3 (process step). No header is inferred.
- **Same color as steps**: Facilitator used the same color for header and steps (user error). Tool treats it as Tier 3. Facilitator corrects the label in the Review UI — this is a legitimate UI use case, not an analyzer failure.

**Output**: Stored as `lane_label` on the workflow group. Rendered as a column/row heading in the PDF. Not assigned to the workflow sequence.

### Tier 3 — Rectangular Process Step (sequence normally)
Any rectangle that does not meet Tier 1 or Tier 2 criteria. Treat as a normal workflow step.

### Key Rules
- **Size is the Tier 1 discriminator**: A banner is always larger. If it's standard note size, it is Tier 2 or Tier 3.
- **Color is the Tier 2 discriminator**: The entry-point note of a group (topmost for vertical, leftmost for horizontal) whose color matches the modal color of the group's remaining notes is a process step, not a header.
- **Modal color, not any color**: Compare against the most frequently occurring color in the column, not just "different from any other note." A mid-sequence pain point or decision note in an outlier color does not disqualify the header check.
- **Shape string alone is insufficient**: Both squares and rectangles can be Tier 2 headers. `is_rectangle_shape()` must be extended to include `'square'` for header detection purposes.
- **Position confirms, size decides for Tier 1**: A large rectangle mid-sequence that somehow passes the size check should still be treated as Tier 3 if it fails the Y-position and column-gap tests.
- **Applies to all layout types**: Banner and lane header detection runs before layout-specific grouping logic for all four layout types.

---

## Detection Logic Hierarchy

```
1. LAYOUT CLASSIFICATION (User selects at upload)
   ↓
1b. RECTANGLE ROLE PRE-PASS (Before grouping)
   - Identify Tier 1 banners → extract as process_title, remove from note pool
   - Identify Tier 2 lane headers → tag as lane_label, remove from note pool
   - Remaining notes → proceed to grouping
   ↓
2. WORKFLOW GROUPING (Based on layout type)
   - Single Column: All notes → 1 workflow
   - Newspaper: All notes → 1 workflow (but column-aware sequencing)
   - Horizontal Lanes: Group by Y-gaps → N workflows
   - Vertical Lanes: Group by X-gaps → N workflows
   ↓
3. PER-WORKFLOW ANALYSIS (Applied to EACH workflow independently)
   ↓
   3a. PARALLEL DETECTION
       - Compare Y-coordinates within same workflow
       - Notes within ±30px AND side-by-side = PARALLEL
       - Both notes marked with parallel_with: partner_id
   ↓
   3b. DECISION BRANCH DETECTION
       - Find diamond shapes
       - Yes branch: Closest note to RIGHT (>50px right, within 150px Y)
       - No branch: Closest note BELOW (>50px down, within 200px X)
       - Rejoin: First note below where both branches end
   ↓
   3c. SEQUENCING
       - Single Column: Sort by Y-coordinate
       - Newspaper: Sort by column, then Y within column
       - Horizontal Lane: Sort by X-coordinate
       - Vertical Lane: Sort by Y-coordinate
   ↓
4. PDF RENDERING
   - Draw notes with correct shapes/colors
   - Render parallel steps side-by-side
   - Draw decision branches with labeled arrows
   - Show convergence points where branches rejoin
```

---

## Critical Rules

### Parallel Detection
1. **Must be same workflow** - Never mark notes in different workflows as parallel
2. **Must be same Y-level** - Within ±30px vertically
3. **Must be side-by-side** - Horizontally adjacent (not separated by other notes)
4. **Reciprocal relationship** - If Note A parallel with Note B, then Note B parallel with Note A
5. **Skip headers** - Rectangular notes at top (Y < 20% of image height) are not parallel candidates

### Decision Branches
1. **Only diamond shapes** - No other shape triggers decision logic
2. **Must have branches** - At least one of Yes/No paths must be identifiable
3. **Spatial relationships**:
   - Yes = to the RIGHT of diamond
   - No = BELOW diamond (continuing main flow)
4. **Rejoin required** - Both paths should converge at a common step
5. **Follow arrows** - If hand-drawn arrows visible, they override spatial heuristics

### Workflow Grouping
1. **Gap-based detection** - Use spatial gaps to identify separate workflows
2. **Thresholds**:
   - Horizontal lane gap: >100px vertical
   - Vertical lane gap: >150px horizontal
3. **Headers matter** - Rectangular notes at boundaries often indicate lane headers
4. **User override** - Layout type selection overrides automatic detection

---

## Edge Cases & Known Issues

### 1. Ad-hoc Branches (e.g., "for Mexico...")
**Scenario**: A single note branches off main flow but isn't a full parallel path
**Current Handling**: May be detected as parallel or separate workflow
**Desired Behavior**: Should be treated as optional side branch, not new workflow
**Status**: Needs refinement

### 2. Overlapping Photos in Multi-Photo Mode
**Scenario**: Detail photos overlap with overview photo
**Current Handling**: Matching algorithm attempts to link detail→overview
**Known Issues**: Can produce duplicate notes or mismatches
**Status**: Requires testing and tuning

### 3. Background Objects
**Scenario**: Framed photos, whiteboards, other objects visible in image
**Current Handling**: May be detected as notes
**Desired Behavior**: Ignore non-note objects
**Status**: Prompt engineering needed

### 4. Handwriting Legibility
**Scenario**: Poor handwriting or low-res photos
**Current Handling**: Claude returns "UNREADABLE" for unclear text
**Desired Behavior**: Allow manual correction in review UI
**Status**: Working as designed

### 5. Arrow Detection
**Scenario**: Hand-drawn arrows between notes
**Current Handling**: Partially - Claude can identify arrow target coordinates
**Desired Behavior**: Use arrows to override spatial heuristics
**Status**: Implemented but needs testing

---

## Success Criteria

### Minimum Viable Product (MVP)
- ✅ Single-column workflows with parallel steps
- ✅ Decision diamonds with Yes/No branches
- ✅ Basic PDF generation
- ✅ Manual editing in review UI

### Production Ready (v1.0)
- ✅ All 4 layout types supported
- ✅ Coordinate-based detection (not text descriptions)
- ✅ Multi-photo stitching for wall workflows
- ⏳ 80%+ accuracy on test cases
- ⏳ Deployment to cloud (Render or Railway)

### Future Enhancements (v2.0+)
- ⏳ Arrow-following detection (ignore position heuristics)
- ⏳ Auto-detect layout type (no user selection needed)
- ⏳ Export to Visio/Lucidchart
- ⏳ Collaborative editing (multiple users)
- ⏳ Video input (scan wall with phone, extract frames)

---

## Technical Constraints

### Vision API Limitations
- **Token limit**: 2000-4000 tokens per request (affects large images)
- **Truncation**: Response may be cut off if too many notes
- **Bounding box accuracy**: ±10-20px expected error
- **Arrow detection**: Can identify but not perfectly precise

### PDF Rendering Constraints
- **ReportLab**: Limited to basic shapes (no curved arrows)
- **Page size**: Must calculate dynamically based on note count
- **Diamond rendering**: Requires custom path drawing

### Performance
- **Single photo**: ~5-10 seconds (Claude API call)
- **Multi-photo**: ~30-60 seconds (multiple API calls + matching)
- **PDF generation**: <5 seconds

---

## Testing Requirements

See **TEST_CASES.md** for detailed test scenarios.

Minimum test coverage:
1. Single column with parallel steps (Test Case 1)
2. Newspaper columns without false parallels (Test Case 2)
3. Decision diamond with proper Yes/No routing
4. Horizontal swim lanes (if applicable)
5. Vertical swim lanes (if applicable)

---

## User Experience Requirements

### Upload Flow
1. User selects layout type (4 radio buttons)
2. User uploads 1 or more images
3. System analyzes and shows progress
4. User reviews detected notes in UI
5. User can edit text, relationships, sequence
6. User generates PDF

### Review UI Must Support
- Edit note text
- Delete notes
- Mark notes as parallel (click two notes)
- Set decision branches (click diamond, then Yes note, then No note)
- Reorder sequence (drag-and-drop)
- Merge duplicate notes
- Add missing notes manually

### Output Options
- Download PDF
- Save to Google Drive
- Email to recipients
- Export raw JSON data

---

## Maintenance & Updates

This document should be updated when:
- New layout type identified
- Detection rules refined based on testing
- Edge cases discovered
- User feedback received
- API capabilities change (Claude model updates)

Last Updated: 2026-02-08
