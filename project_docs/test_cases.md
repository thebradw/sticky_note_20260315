# Test Cases for Sticky Note Analyzer

## Test Case 1: One Column Newspaper Decision Diamond with Parallel Steps
**Status**: passed 02/12/2026 8:19 PM EST / passed 2/21/26 9:31PM
**Image**: newspaper_1header_decision.jpeg

### Frame Context
**Contains Multiple Workflows**: YES
- Primary workflow: "Elec/Mech Flow" (center/left of frame)
- Secondary workflow: Partially visible on right edge (OUT OF SCOPE for this test)

**Multi-Photo Context**:
This image would be photo 1 of 3 in a full wall capture:
- Photo 1 (this): "Elec/Mech Flow" complete, next workflow partially visible
- Photo 2 (right): Would show the workflow currently at right edge
- Photo 3 (future): Additional workflow not visible in this image

**Boundary Definition**:
Tool should process ONLY the "Elec/Mech Flow" workflow because:
- Clear header note present
- Forms complete vertical column
- Right-edge notes spatially separated (>6 inches horizontal gap)

**Expected Single-Upload Behavior**:
- Ignore right-edge workflow
- Output only "Elec/Mech Flow" hierarchy
- Multi-photo mode: Use right-edge notes as alignment markers for stitching

---

### Expected Output

**Visual Layout**:
- Header note isolated at top
- Main column flows vertically down center
- One pair of notes horizontally aligned (Child02 and Child03)
- Diamond shape appears at Child09
- Two notes branch from diamond: one right (Yes path), one below (No path)
- Branches reconverge before continuing vertical flow

**Detection Criteria**:
- Y-coordinates of "Eng review" and "order entry" within ~30px (parallel detection)
- Diamond shape recognition (width ≈ height, rotated 45°)
- Two notes connected from decision node
- Reconvergence point where both branches feed into single note

**Hierarchy**:
```
Parent: "Elec/Mech Flow"
├─ Child01: "Sales PO"
├─ Child02: "Eng review" (parallel with Child03)
├─ Child03: "order entry" (parallel with Child02)
├─ Child04: "Quality review"
├─ Child05: "Purchase items"
├─ Child06: "Eng. Preps test procedures"
├─ Child07: "Rec Production items"
├─ Child08: "Lab Testing"
├─ Child09: "Mat'l test req?" (DECISION - Diamond shape)
│   ├─ YES → "Mat. Lab (~50%)"
│   └─ NO → (continues to Child10)
├─ Child10: "Test report review by Eng & QA" (receives both decision paths)
├─ Child11: "Final Inspection & Doc"
└─ Child12: "Shipping"
```

**Critical Pass Criteria**:
- [ ] "Elec/Mech Flow" identified as parent/header
- [ ] Child02 and Child03 detected as parallel (not sequential)
- [ ] Diamond shape triggers decision branch logic
- [ ] Both decision paths (Yes/No) properly tracked
- [ ] Decision branches reconverge at Child10
- [ ] Right-edge workflow notes excluded from output
- [ ] Total step count: 1 parent + 12 children (not 13+ from secondary workflow)

**Known Issues to Watch**:
- Hand-drawn arrows vary in quality - tool should rely on spatial proximity
- Decision "No" path has no explicit sticky note - tool should infer direct connection to Child10
- Partial notes at right edge should not be interpreted as part of primary workflow

**Root Causes Fixed 2/21/26**:
1. `analyze_workflow` used `max_tokens=2000` — too low for 15-note images; diamond near bottom was truncated from JSON. Fixed: raised to 4096.
2. T3.0 `classify_rectangle_roles` detected the background rectangle behind the "Elec/Mech Flow" sticky as the Tier 1 banner and accepted Claude Vision's hallucinated text on it as the title. Fixed: added "sticky-on-background" pattern — when the Tier 1 banner is `rectangular`, scan for a non-rectangular sticky overlapping it and use that sticky's text instead. Added secondary fallback for single-column/newspaper: if no banner found, the topmost vertically-isolated note becomes the title.

---------------------------------------------------------------------------------

## Test Case 2: Newspaper with columns No Header
**Status**: good enough, 3/6/2026
**Image**: newspaper_noheader_decision.jpeg

### Frame Context
**Contains Multiple Workflows**: NO

**Multi-Photo Context**:
This image is the only workflow. No other pictures or reference to other workflows

**Boundary Definition**:
Tool should process all sticky notes in the  workflow:
- No header note present
- Forms mulit vertical columns
- Decision diamond does not have clear Yes/No ouputs

### Expected Output

**Visual Layout**:
-  Multiple columns, one straight workflow
- Diamond shape appears at #
- Daimond note placed in non-logical location.  It is meant as a standalone failure point if the workflow "spins"
- 4 non-recatangle, non-square stickies represent "Pain Points" in the system.  Should be recorded as "Pink" color and associated with a process step as defined in Hierarchy in this document

**Detection Criteria**:
- Begin with top left sticky "Inter-Company"
- Diamond shape recognition (width ≈ height, rotated 45°)
- Star shape recognition (any shape not a square or rectangle)
- Start top left, go down. follow arrows drawn on sticky notes.  1 add hoc note 06: "for Mexico..." branches left parallel to 05"Auto create sals order". Go down to end of column, follow arrows drawn on sticky note to right and stay at the bottom sticky in column two. Now go up to the top of the column.  Go to right and stay at the top sticky in column three, then go down the column.  End at the diamond. 

**Hierarchy**:

Parent: None
├─ 01: "Inter Company  Orders -Europe - Asia"
├─ 02: "receive orders - by email"
├─ 03: "Enter in QAD"
│   ├─ PainPt1: "input errors"
├─ 04: "auto create PO"
├─ 05: "Auto create sales order" (follow arrow to left)
├─ 06: "for Mexico go to SOW"
├─ 07: "create PO for contract mfg"
├─ 08: "Send PO to mfg"
├─ 09: "mfg SO acknowledge -email" 
├─ 10: "Ship requirement with Forwarder"
├─ 11: "Confirmed & booked with Forwarder"
├─ 12: "Pick list of lots"
├─ 13:"Create Loading docs  -Access D.B. -Duplicate transport D.B."
├─ 14:"Collection -Product for cust. - take ownership of mat'l"
├─ 15:"close order -QAD"
├─ 16:"Auto fills PO when works" (ignore scratched out letters)
│   ├─ PainPt2:"If fails do manually"
│   ├─ PainPt3:"Phantom Demand"
├─ 17:"Close SO"
│   ├─ PainPt4:"All data resides in unique D.B. -Hard to analyze"
└─ 18:"can't do it" with spiral drawing ( Diamond shape)

**Critical Pass Criteria**:
- [ ] Follow flow directions as defined in Detection Criteria
- [ ] 06 is to the left of 05
- [ ] Total step count: 0 parent + 18 steps + 4 paint points properly nested

**Known Issues to Watch**:
- Hand-drawn arrows vary in quality - tool should rely on spatial proximity
- Pain Point stickies are out of alignment to work flow. This is by design, and should be assigned to nearest sticky note.
- Background is a framed photograph of a chicken.  Background images should be ignored.

**Overlapping Sticky Notes — Decision Record (2026-03-06)**:

*Problem*: Step 16 ("Auto fills PO when works") and PainPt2 ("If fails do manually") are a green square with a pink star placed directly on top of it. Vision was merging them into a single note with garbled combined text.

*Fix applied*: Two prompt changes in `analyze_workflow` (`image_analyzer.py`):
1. Added CRITICAL OVERLAP RULE to the shape classification instructions — explicit instruction that a non-standard shape overlapping a square note is always two separate JSON entries.
2. Added a worked overlap example to the JSON template using exactly this note pair as the example.

*Result*: Pain points that are adjacent or partially overlapping (e.g. PainPt1, PainPt3, PainPt4) are correctly separated. The full-cover case (PainPt2 star placed directly on top of the square, obscuring its text) still merges because Vision cannot recover the underlying text when it is physically hidden.

*Decision*: Full-cover overlap is out of scope for code fixes. Facilitator guideline: anchor pain point stickies to the edge of the process note — do not stack them on top. A few centimeters of offset is sufficient for correct detection.
------------------------------------------------------------------------

## Test Case 3 (T3.0): Rectangle Role Classifier — Vertical Swim Lanes with Banner and Lane Headers
**Status**: passed 2/28/2026
**Image**: `test_images/two_vertical_flows.jpg`
**Implements**: `classify_rectangle_roles()` pre-pass added in T3.0

### Frame Context
**Contains Multiple Workflows**: YES — two vertical swim-lane columns

**Layout**:
- One large rectangular banner at the top ("Obtain PO") — yellow/white, visibly wider than all process step notes
- Two columns of sticky notes below the banner
- Column A (left): purple/pink square lane header ("Capital") at top, then 5 orange square process steps below
- Column B (right): purple/pink square lane header ("Inventory") at top, then 2 orange square process steps below
- Lane headers are a distinctly different color (purple/pink) from the orange process steps

### Expected Classifier Output

**Tier 1 — Banner**:
- "Obtain PO" rectangle detected because: `width >= 1.5 × median_width` AND `center_y <= 0.2 × max_y` (top 20% of image)
- `process_title` = `"Obtain PO"`
- Banner note **NOT** present in `workflow_sequence` of either group

**Tier 2 — Lane Headers**:
- Column A first note (topmost, purple/pink): `color('purple') != modal_color('orange')` → Tier 2
  - `lane_labels[0]` = `"Capital"`
  - Header note **NOT** in Column A `workflow_sequence`
- Column B first note (topmost, purple/pink): same logic → Tier 2
  - `lane_labels[1]` = `"Inventory"`
  - Header note **NOT** in Column B `workflow_sequence`

**Tier 3 — Process Steps**:

Column A ("Capital") — 5 orange steps, sequenced top-to-bottom:
1. "POR Submittal to manager + finance"
2. "send approved POR to Acctng"
3. "Create PO in Obeer"
4. "email PO + CAR# to requestor"
5. "Send PO to vendor"

Column B ("Inventory") — 2 orange steps, sequenced top-to-bottom:
1. "Create PO in Obeer"
2. "Send PO to vendor"

### Critical Pass Criteria
- [ ] `analysis['process_title']` == `"Obtain PO"` (not `None`)
- [ ] Banner note ID not present in `workflow_sequence` of either group
- [ ] `analysis['workflows'][0]['lane_label']` == `"Capital"`
- [ ] `analysis['workflows'][1]['lane_label']` == `"Inventory"`
- [ ] Column A lane header note ID not in `analysis['workflows'][0]['note_ids']`
- [ ] Column B lane header note ID not in `analysis['workflows'][1]['note_ids']`
- [ ] `len(analysis['workflows'][0]['note_ids'])` == 5
- [ ] `len(analysis['workflows'][1]['note_ids'])` == 2
- [ ] Steps within each column sequenced top-to-bottom by center_y

### PDF Output Assertions
- [ ] Bold title "Obtain PO" (Helvetica-Bold 14pt) rendered above all content
- [ ] 12pt gap between title and first lane
- [ ] Bold lane label "Capital" (Helvetica-Bold 11pt) rendered above Column A's first note
- [ ] Bold lane label "Inventory" (Helvetica-Bold 11pt) rendered above Column B's first note
- [ ] 8pt gap between each lane label and its first note
- [ ] Lane header notes do not appear as process step boxes in PDF
- [ ] Banner note does not appear as a process step box in PDF

### Threshold Sensitivity Notes
- Tier 1 size threshold: `>= 1.5 × median`. If banner is only 1.3× median, it will not be detected → Tier 3 (expected fallback, not a bug).
- Tier 1 position threshold: `center_y <= 0.2 × max_y`. Banner must be in top 20% of image height.
- Tier 2 color comparison: exact string match on `note['color']`. If Vision API returns the same color string for both header and steps, no Tier 2 detection occurs (expected edge case — facilitator error, UI fix).
- Single-note groups: always Tier 3. No lane label extracted.

### Synthetic Unit Test (supplement to photo test — geometry pre-computed to match two_vertical_flows.jpg proportions)
```python
notes = [
    # Tier 1: Banner (wide, top of image)
    {'id': 1, 'text': 'Obtain PO', 'color': 'yellow',
     'shape': 'rectangular', 'center_x': 500, 'center_y': 40,
     'width': 850, 'height': 80, 'bbox': [75, 0, 925, 80]},
    # Tier 2: Column A header (purple, topmost in left column)
    {'id': 2, 'text': 'Capital', 'color': 'purple',
     'shape': 'square', 'center_x': 200, 'center_y': 160,
     'width': 100, 'height': 100, 'bbox': [150, 110, 250, 210]},
    # Tier 3: Column A process steps (orange) — 5 notes
    {'id': 3, 'text': 'POR Submittal to manager + finance', 'color': 'orange',
     'shape': 'square', 'center_x': 200, 'center_y': 290,
     'width': 100, 'height': 100, 'bbox': [150, 240, 250, 340]},
    {'id': 4, 'text': 'send approved POR to Acctng', 'color': 'orange',
     'shape': 'square', 'center_x': 200, 'center_y': 420,
     'width': 100, 'height': 100, 'bbox': [150, 370, 250, 470]},
    {'id': 5, 'text': 'Create PO in Obeer', 'color': 'orange',
     'shape': 'square', 'center_x': 200, 'center_y': 550,
     'width': 100, 'height': 100, 'bbox': [150, 500, 250, 600]},
    {'id': 6, 'text': 'email PO + CAR# to requestor', 'color': 'orange',
     'shape': 'square', 'center_x': 200, 'center_y': 680,
     'width': 100, 'height': 100, 'bbox': [150, 630, 250, 730]},
    {'id': 7, 'text': 'Send PO to vendor', 'color': 'orange',
     'shape': 'square', 'center_x': 200, 'center_y': 810,
     'width': 100, 'height': 100, 'bbox': [150, 760, 250, 860]},
    # Tier 2: Column B header (purple, topmost in right column)
    {'id': 8, 'text': 'Inventory', 'color': 'purple',
     'shape': 'square', 'center_x': 650, 'center_y': 160,
     'width': 100, 'height': 100, 'bbox': [600, 110, 700, 210]},
    # Tier 3: Column B process steps (orange) — 2 notes
    {'id': 9, 'text': 'Create PO in Obeer', 'color': 'orange',
     'shape': 'square', 'center_x': 650, 'center_y': 290,
     'width': 100, 'height': 100, 'bbox': [600, 240, 700, 340]},
    {'id': 10, 'text': 'Send PO to vendor', 'color': 'orange',
     'shape': 'square', 'center_x': 650, 'center_y': 420,
     'width': 100, 'height': 100, 'bbox': [600, 370, 700, 470]},
]
# Expected: process_title='Obtain PO'
# Expected: lane_labels == {0: 'Capital', 1: 'Inventory'}
# Expected: cleaned_notes IDs == [3, 4, 5, 6, 7, 9, 10]
```
------------------------------------------------------------------------
------------------------------------------------------------------------
---------------------------------------------------------------------------------

## Test Case 4: Horizontal workflow Single photo
**Status**: partial pass 2026-03-15 — pipeline runs clean; lane-1 merge and weak OCR on headers 2–4 are photo-quality limits (see Known Issues below)
**Image**: leftright_headers_swimlane_painpoint.jpeg

### Frame Context
**Contains Multiple Workflows**: No

**Multi-Photo Context**:
This image is the only workflow. No other pictures or reference to other workflows

**Boundary Definition**:
Tool should process all sticky notes in the  workflow:
- 5 header notes present
- Forms multiple horizontal columns
- Pain points are aligned under the square sticky notes

### Expected Output

**Visual Layout**:
- Multiple columns, 5 straight workflows
- 12 non-recatangle, non-square stickies represent "Pain Points" in the system.  Should be recorded as "Blue" color and associated with a process step as defined in Hierarchy in this document

**Detection Criteria**:
- Begin with top left sticky "Data Flow"
- Callout shape recognition (any shape not a square or rectangle)
- Start top left, go right.  At end of right most row, go down and right again until end 

**Hierarchy**:

Parent1: "Data Flow"
├─ 01: "PO for materials in Obeer"
├─ 02: "QSA - track inv & assign lot # - Obeer & QSA" (ignore stratch out squibbles after QSA)
├─ 03: "QSA pushes Lot data to Azure"
├─ 04: "Reporting - inventory from Obeer - Prod. Orders in Obeer - S.O. - P.O"
Parent2: "Prod. Data Flow"
│   ├─ PainPt1: "want to own the data, where stored doesn't matter"
├─ 05: ""Expressions" in Obeer consume BOM from Obeer"
│   ├─ PainPt2: "Obeer can't handle compliance for beer & spirits"
├─ 06: "Data dump into excel -MRP excel workaround"
│   ├─ PainPt3: "MRP in Obeer identifying outbound qty discrepancies"
├─ 07: "Brewing QSA has recipe & brew sheet"
│   ├─ PainPt4: "no data out of brew-house"
├─ 08: "consume lots out of QSA"
│   ├─ PainPt5: "double entry in Obeer & QSA to make a beer"
├─ 09: "collect info about brew & enter into QSA" 
│   ├─ PainPt6: "manual data entry"
├─ 10: "Cellar Have IoT input data into Azure"
├─ 11: "Bridge to moderate needed in Azure.  Scada system tank & packaging info
│   ├─ PainPt7: "can improve Scada fitters"
├─ 12: "Lab in Cellar Lab data is pushed into excel & linked to QSA"
├─ 13: "Cellar putting data into QSA"
│   ├─ PainPt8: "manual lot tracking & doesn't match Obeer"
│   ├─ PainPt9: "All inventory should only reside in the ERP"
├─ 14:"PKG input prod. volume into QSA & Prod. Mngr puts into Obeer"
│   ├─ PainPt10: "double entry"
Parent3: "Prod. Sched. Data = Obeer does this weel"
├─ 15: "copy this schedule/route/storage logic & edit items"
Parent4: "Sales Order Data Flow"
├─ 16: "Idig -shows historical drawdowns @ customer"
├─ 17:"manual data pulls from Idig to Azure"
│   ├─ PainPt11: "Idig does not have API"
├─ 18:"Order Analysis custom SQL reports built in Obeer - All invoices - Open SO Used to decide future / next order amounts" (two square stickies, but all text belongs in 1 square)
├─ 19:"Idig deplesion data & Obeer SO qty. To compare forecast demand to actual sales. So cust doesn't run out"
│   ├─ PainPt12: "building this report is not scalable"
├─ 20: "notify SDC of our recommended qty = restart SO process"
├─ 21: "Karma SRM survey tool - pictures - freshness at site -data cleaning - load into Azure - Power BI reports"
├─ 22: "keep VIP tools"
Parent5: "Forecast Data Flow"
├─ 23: "build forecasts in excel"
├─ 24: "place in Azure"
└─ 25: "poll when needed"

**Critical Pass Criteria**:
- [ ] Follow flow directions as defined in Detection Criteria
- [ ] seperate workflows for each parent
- [ ] Total step count: 5 parents + 25 steps + 12 paint points properly nested

**Known Issues to Watch**:
- Top left header sticky "Data Flow" is cut off in the picture.  This is a header.
- Pain Point stickies are out of alignment to work flow. This is by design, and should be assigned to nearest sticky note.
- steps 11,18,19 uses two sticky notes for one process step.  Tool should place all text into one step in the output
- step 21 uses 4 sticky notes as a list of items in the process step. Tool should place all text into one step in the output
- Text contains ancronyms such as "Idig".  Tool should return exact lettering of text, and not hallucinate or assume word is misspelled

**Run 3 findings (2026-03-15)**:
Fixes confirmed working:
- `flow_direction=horizontal-swim-lanes` auto-detected by diagnose script (no longer defaults to wrong layout)
- No JSON parse crash (Unicode `≥` char in print statement replaced with `>=`)
- T3.0 Tier 1 banner correctly suppressed (`[T3.0] Tier 1 banner skipped` confirmed)
- `is_workflow_title` priority in T3.0 Tier 2 header election working — "Data Flow" (header cut off at image edge, not leftmost X) now correctly elected via flag instead of leftmost-note fallback
- Pain points detected with `is_pain_point=True`, `speech-bubble` shape, and `pain_point_for` anchoring

Remaining photo-quality limits (not code bugs):
- Rows 1 and 2 (expected "Data Flow" and "Prod. Data Flow") share the same Y band in this photo — both land at cy≈86, gap is below the 72px `LANE_GAP_HORIZONTAL` threshold. The two rows merge into a single 13-step lane. Fix: retake the photo with more vertical spacing between those two swim lanes, or zoom in to separate shots.
- Lane headers for rows 2–4 return garbled text ("enable aging", "[illegible]") because the handwriting on those yellow rectangulars is too small at this resolution. Fix: retake at higher resolution or crop closer.
- Several process-step texts partially garbled (e.g., "Expressions in beer Carmel" vs. expected "Expressions in Obeer consume BOM") — same root cause.
- Row 3 (T3.0): "SRM Survey Tool" evaluated as lane header candidate but is actually a process step; the true lane header for that row is missing/unreadable. Use Review UI to correct if needed.

------------------------------------------------------------------------
------------------------------------------------------------------------
---------------------------------------------------------------------------------

## Test Case 5: Horizontal workflow Single photo version2
**Status**: functional pass 2026-03-15 — 2 workflows detected, 9 pain points anchored, ~2-3 Review UI edits needed (Cellar label illegible; step 14 multi-sticky creates overflow lane)
**Image**: horizontal_brewer_cellar.jpg  *(file added to test_images/; _LAYOUT_DEFAULTS entry added)*

### Frame Context
**Contains Multiple Workflows**: No

**Multi-Photo Context**:
This image is the only workflow. No other pictures or reference to other workflows

**Boundary Definition**:
Tool should process all sticky notes in the  workflow:
- 2 header notes present
- Forms 2 horizontal columns
- Pain points are aligned under the square sticky notes. Two of these pain points are aligned under the sticky note "cellar" from the bottom left point of the sticky note.

### Expected Output

**Visual Layout**:
- Multiple columns, 2 straight workflows
- 9 non-recatangle, non-square stickies represent "Pain Points" in the system.  Should be recorded as "Blue" color and associated with a process step as defined in Hierarchy in this document

**Detection Criteria**:
- Begin with top left sticky "Brewing"
- Callout shape recognition (any shape not a square or rectangle)
- Start top left, go right.  At end of right most row, go down and right again until end 

**Hierarchy**:

Parent1: "Brewing"
├─ 01: "Pipeline meeting - forecast - orders for next week and the week after - be on the lookout/oddities." (Contains two sticky notes that are one process step)
├─ 02: "Update batch sizes & time slot items in prod. Order in Obeer."
├─ 03: "Prep Additives & Stage Materials"
├─ 04: "Mill first batch - enter material in QSA "brew sheet""
├─ 05: "Add ingredients as called for - update QSA with actual amounts used."
├─ 06: "Wind tank full - Review QSA -enter data Obeer"
│   ├─ PainPt1: "Like for brewers to be able to input data in the system"
│   ├─ PainPt2: "Input & save for approval later before "express""
│   ├─ PainPt3: "Raw material lot number may not be in Obeer -Hops."

Parent2: "Cellar" 
│   ├─ PainPt4: "Need a real-time feedback loop to planning & pkg about over or under prod."
│   ├─ PainPt5: "Auto Alerts sent for Variance Tolerance"
├─ 07: "Same pipeline meeting."
├─ 08: "Manage Yeast - 2 Excel files - crop - st yeast request log"
│   ├─ PainPt6: "Manual feedback loop on changes @ S.T. for yeast needs."
├─ 09: "Update seller task list - Word doc "rolling schedule"" 
│   ├─ PainPt7: "Build into the ERP schedule."
├─ 10: "Do task list"
├─ 11: "Express mat'ls in Obeer"
├─ 12: "Update QSA w/ fruit usage."
├─ 13: "Evaluate hops - designate 'hot' or 'cold' side in "Inv. Tracker"."
│   ├─ PainPt8: "Hops eval not listed on sheet"
├─ 14:"Move liquid to bright tank. Record data in QSA:
- vol in
- vol out
- # injections
- time start/end
- carbonation & other beer specs
- center fuge system can input vol. data in QSA." (Three stickies as one process step)
│   ├─ PainPt9: "QSA Down. no cust. Support. need a replacement"
└─ 15: "Manager reviews data & inputs into Obeer."

**Critical Pass Criteria**:
- [ ] Follow flow directions as defined in Detection Criteria
- [ ] seperate workflows for each parent
- [ ] Total step count: 2 parents + 15 steps + 9 paint points properly nested

**Known Issues to Watch**:
- Pain Point stickies are out of alignment to work flow. This is by design, and should be assigned to nearest sticky note.
- steps  1 uses 2 sticky notes for one process step.  Tool should place all text into one step in the output
- step 14 uses 3 sticky notes as a list of items in the process step. Tool should place all text into one step in the output
- Text contains ancronyms and company names such as "Obeer".  Tool should return exact lettering of text, and not hallucinate or assume word is misspelled

**Run findings (2026-03-15)**:
Fixes confirmed working:
- `_header_only_lane()` fix: Cellar header (yellow rectangular, is_workflow_title=True) sat in inter-lane gap with one stray pain point (len==2). New fix correctly identifies it as header-only and forwards label to Cellar process-step lane. Console: `[T3.0] Isolated Tier 2 header (lane 2) -> lane 3: '[illegible]'`
- 2 workflows correctly detected (down from 4 orphan lanes pre-fix)
- 9 pain points detected and anchored (matches expected total)
- Step 1 two-sticky merge working: Vision correctly combined both stickies into one note
- OCR quality meaningfully better than TC4 -- most step texts partially recognizable

Remaining photo-quality limits (not code bugs):
- Cellar lane label comes through as "[illegible]" -- Vision cannot read the header handwriting. 1 Review UI edit to rename the lane.
- Several Cellar step texts garbled (step 4, 6, 8 area). ~2 Review UI edits to correct.
- Step 14 (3-sticky note) lower stickies fall below the Cellar pain-point row, creating a 3rd orphan workflow containing note 20 + 2 pain points. Use Review UI to merge step 14 content and move pain points. This is a known multi-sticky limitation.
- 2 pain points (IDs 23-24) land in the overflow lane with no anchor -- PainPt4 and PainPt5 from the expected hierarchy. Acceptable; anchor manually in Review UI.



## Test Case 5 (T4.0): Multi-Photo Horizontal Wall — Geometric Registration
**Status**: pass 2026-07-02 — merge pipeline validated end-to-end after coordinate-space, gate, dedup, and arrow-stripping fixes; residual items are wall-content ambiguities, not code bugs. API integration test, MANUAL RUN ONLY (offline coverage: `test_registration.py`)
**Images**: `leftright_wholewall.jpeg` (overview) + `child1_wallcloseup.jpeg`, `child2_wallcloseup.jpeg`, `child3_wallcloseup.jpeg` (details)
**Layout**: `horizontal-swim-lanes`

### Frame Context
**Contains Multiple Workflows**: Yes (wide wall, horizontal rows)

**Multi-Photo Context**:
One wide-angle overview of the full wall plus three overlapping close-ups covering the left, middle, and right thirds. Overview text is largely unreadable at wall scale; the close-ups supply text. This is the fixture set T4.0 was validated on: child1/2/3 register at 24/58/82% of overview width (left → middle → right).

**Boundary Definition**:
- Overview supplies note positions (pixel bboxes in the 4000px Vision space)
- Detail photos supply text, color, shape — text is payload, never a matching signal
- Detail bboxes transform into overview space via SIFT/RANSAC homography (`registration.py`); matching is nearest-neighbor by center distance (`match_by_geometry`)

### Expected Output

**Registration (deterministic, no API)**:
- All three child photos register with `status='ok'` (baseline: 480/57/45 inliers, ratios 77/26/23%)
- Registration failures on any child photo indicate a code regression, not photo quality — see `test_registration.py`

**Detection Criteria / Pass Assertions**:
- [ ] No duplicate notes: no two merged notes with center distance < 0.5 x median note width
- [ ] `workflow_sequence` ordering consistent with left-to-right wall order (child1's notes before child2's before child3's within each lane)
- [ ] Text for `source='registered'` notes comes from the detail photos (higher-resolution observation), not the overview pass
- [ ] T3.0 lane headers elected (rectangle-shaped, color-contrast or is_workflow_title signals) and excluded from `workflow_sequence`
- [ ] Merged notes flow through the unified pipeline: `workflows` metadata present, notes carry `center_x`/`center_y` in overview space
- [ ] Unmatched detail notes (overview pass misses on dense walls) inserted as `source='detail_registered'` with confidence 85 — these are expected, not errors

**Confidence Expectations**:
- Registered merges: `min(99, 60 + inlier_ratio * 40)` — approx. 91 (child1), 70 (child2), 69 (child3)
- Legacy-fallback merges (should be none on this fixture set): capped at 60 with `low_confidence=True`
- Overview-only notes: 50

### How to Run
```bash
# Requires ANTHROPIC_API_KEY in .env — coordinate before running (quota)
python - <<'PY'
from image_analyzer import StickyNoteAnalyzer
a = StickyNoteAnalyzer()
result = a.process_multi_photo_session(
    "test_images/leftright_wholewall.jpeg",
    ["test_images/child1_wallcloseup.jpeg",
     "test_images/child2_wallcloseup.jpeg",
     "test_images/child3_wallcloseup.jpeg"],
    flow_direction="horizontal-swim-lanes")
PY
```

**Run findings (2026-07-02, final validation run)**:
- Registration (deterministic): child1/2/3 = 435/62/36 inliers, ratios 79/36/20%, centers 24/58/82% of overview width. All three pass the redesigned gates (statistical floors + geometric plausibility); the unrelated-pair impostor is rejected by the plausibility gate (collapsed non-convex quad).
- Detection: 120 overview notes + 81 detail notes (Vision counts vary a few notes run-to-run without temperature=0).
- Merge: 61/81 detail notes geometrically matched (max_dist 49px); 13 overlap duplicates resolved by the dedup pass with audit logging; 7 unmatched detail notes inserted as new. Final pool 125 process steps + pain points after T3.0 removed 2 lane headers. Sources: 58 registered / 7 detail_registered / 59 overview_only / 0 legacy fallback.
- Duplicate criterion (< 0.5 x median width): 5 flagged pairs, all legitimate adjacencies on inspection (pain-point-on-step, distinct same-text pain points, dense neighbors). Down from 18 pairs before the dedup pass.
- Text-dissimilarity veto regression check: 'Verify check #' and 'Closes invoice in Obeer' — both destroyed by pure-geometric dedup in the first run — now coexist with their close neighbors ('Print Checks in Doc. Printing', 'Creates outgoing Payments in Obeer'). Veto pairs are asserted in test_registration.py [5].
- T3.0: lane headers 'Finance' and 'no PO' elected (arrow annotation stripped from the latter); 105-step workflow_sequence; all 8 decision diamonds carry arrow-free text with decision_branches intact.

**Confirmed limitations (photo-verified 2026-07-04)**:
- **Lane-gap fragmentation (code limitation — deferred to T3.1)**: Workflow 2 in the last run was a spurious 2-note stub ("need Approved vendor" pain point + "Drag PDF into yooz" step; avg Y 672; both `registered`). Photo verification confirms both notes physically belong to the Finance/AP lane — they are NOT a distinct swim lane. Horizontal-lane Y-gap grouping fragmented them into their own lane because they sit near the Finance↔"no PO" lane boundary where the inter-lane gap is borderline against the threshold. The stub is unlabeled because T3.0 finds no header candidate in it (one pain point + one lone process step → Tier 3). This is a lane-gap threshold behavior, not a labeling bug; the fix needs a *tunable* gap threshold rather than a hardcoded change, so it is deferred to T3.1 (threshold parameterization). Tracked in `task_plan.md` T3.1.
- **Spurious lane-header promotion when no header exists (T3.0 Tier 2 limitation — protocol mitigation)**: Workflow 4's "Hit Approve" label is a confirmed false promotion, not a detection bug. Photo verification confirms the wall's bottom lane has no header sticky and no color-distinct header candidate nearby. T3.0 Tier 2 has no mechanism to distinguish "no header exists" from "header exists but wasn't detected" — given a lane with zero genuine header candidates it will always promote the nearest color-contrast outlier. This is a coverage/protocol issue, not a code defect. Primary mitigation is field-level (one detail photo per swim lane so each lane has a legible header region); Review-UI correction is the fallback. Tracked in `task_plan.md` T3.1 area.

**Known items to watch (unverified — carried forward)**:
- The overview double-detection (twin 'price discrepancy' diamonds in an earlier run) did not recur in this run, so the overview-straggler dedup screen was not exercised live; its logic is covered by the unit-tested shared helper.
- Two adjacent 'manual task' pain points 28px apart both survived (each matched its own overview position) — plausibly two real stickies (cf. TC4's repeated 'manual' pain points); confirm against the photo.
