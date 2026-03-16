# Newspaper Column Layout Reference

## Overview

The "newspaper" layout describes a workflow that spans multiple vertical columns, read sequentially like a newspaper: top-to-bottom in the first column, then move right to the next column and continue top-to-bottom.

## Flow Pattern

```
Column 1    Column 2    Column 3
┌─────┐     ┌─────┐     ┌─────┐
│  1  │     │  5  │     │  9  │
└─────┘     └─────┘     └─────┘
   ↓           ↓           ↓
┌─────┐     ┌─────┐     ┌─────┐
│  2  │     │  6  │     │ 10  │
└─────┘     └─────┘     └─────┘
   ↓           ↓           ↓
┌─────┐     ┌─────┐     ┌─────┐
│  3  │     │  7  │     │ 11  │
└─────┘     └─────┘     └─────┘
   ↓           ↓           ↓
┌─────┐     ┌─────┐     ┌─────┐
│  4  │─────→  8  │─────→ 12  │
└─────┘     └─────┘     └─────┘

Sequence: 1→2→3→4→5→6→7→8→9→10→11→12
```

## Reading Order

1. **Start**: Top-left note (leftmost column, highest Y-coordinate)
2. **Column flow**: Proceed downward through first column
3. **Column transition**: At bottom of column, move right to top of next column
4. **Continue**: Repeat down-then-right pattern
5. **End**: Bottom of rightmost column

## Key Characteristics

### What Newspaper Layout IS
- Multiple vertical columns side-by-side
- Sequential flow (NOT parallel)
- Each column is a continuation of the previous
- Single workflow spanning multiple columns

### What Newspaper Layout is NOT
- Parallel processes (use single-column for that)
- Multiple independent workflows (use vertical-swim-lanes)
- Left-to-right horizontal flow (use horizontal-swim-lanes)

## Detection Logic

### Column Sorting
```python
# Sort by column first, then by row
workflow_notes.sort(key=lambda n: (get_column_index(n), n['center_y']))
```

Where `get_column_index()` determines which column a note belongs to based on X-coordinate ranges.

### Column Boundaries
Columns are identified by clustering notes with similar X-coordinates:
- Notes within ~100-150px horizontal range = same column
- Gap > 150px = new column boundary

## Common Patterns

### Pattern 1: Three Column Flow
```
Sales Process    Order Fulfillment    Shipping
↓                ↓                    ↓
```

### Pattern 2: Ad-hoc Branch
Sometimes a note branches left/right within a column (like "for Mexico → SOW"):
```
Column 1
┌─────────┐
│ Step 5  │
└─────────┘
    ↓
    ├──→ ┌─────────┐ (optional branch)
    │    │ Special │
    │    │ Case    │
    ↓    └─────────┘
┌─────────┐
│ Step 6  │
└─────────┘
```

This is still newspaper layout - the branch is an exception, not parallel.

## Critical: NO Parallel Detection

In newspaper layouts:
- Notes at the same Y-coordinate in different columns are NOT parallel
- They are sequential steps that happen to align visually
- Parallel detection MUST be disabled for newspaper layouts

**Example:**
```
Column 1         Column 2
┌─────────┐     ┌─────────┐
│ Step 3  │     │ Step 7  │  ← Same Y-coordinate
└─────────┘     └─────────┘
   ↓               ↑
                   │
         NOT parallel!
         Step 7 happens AFTER step 3
```

## User Selection

Users select "Newspaper Columns (Sequential columns)" from the dropdown:
- **Label**: "Newspaper Columns (Sequential columns)"
- **Value**: `newspaper`
- **Description**: "Single workflow split across columns - read down column 1, then down column 2, etc."

## Visual Indicators

When analyzing newspaper layouts, look for:
1. **Multiple vertical groupings** of notes
2. **Consistent column widths** (notes aligned vertically)
3. **Arrows crossing column boundaries** at bottom-to-top transitions
4. **No explicit swim lane headers** (unlike swim lanes)

## Pain Points in Newspaper Layouts

Pain points are annotation notes that highlight issues, bottlenecks, or special cases:

**Identification:**
- ANY non-standard shape (star, oval, circle, cloud, callout, arrow, hexagon, etc.)
- Standard workflow shapes: square, rectangular, diamond
- Everything else = pain point

**Behavior:**
- Don't participate in the sequential flow
- Rendered as offset annotations near their associated step
- No arrows connect to/from them
- Common examples: "Errors", "Bottlenecks", "Manual workarounds", "Phantom Demand"

**PDF Rendering:**
- All pain points rendered as ovals (regardless of original shape)
- Smaller size (70% of normal notes)
- Dashed border, semi-transparent fill
- Positioned to the right of associated workflow step

## Example: Test Case 2

From `test_cases.md`:

```
newspaper_noheader_decision.jpeg

Expected flow:
1. Inter-Company Orders (top-left)
2. Receive Order
3. Enter in QAD
4. Auto create PO
5. Auto create sales order
6. for Mexico → SOW (branch left)
7. create PO for contract mfg
... continues down, then right to next column ...
18. can't do it (spiral drawing - diamond)

Pain Points:
- "input errors" (near step 3)
- "If fails do manually" (near step 16)
- "Phantom Demand" (near step 16)
- "All data resides..." (near step 17)
```

## Implementation Status

✅ Flow direction parameter captured from UI  
✅ Parallel detection disabled for newspaper  
✅ Column-based sorting implemented  
✅ Pain points excluded from flow logic  
⏳ Testing with actual newspaper image  
⏳ PDF verification

## Related Layouts

- **Single Column**: One vertical column with possible parallels
- **Vertical Swim Lanes**: Multiple independent workflows in columns
- **Horizontal Swim Lanes**: Multiple workflows in rows

Each layout type has different parallel detection and sequencing rules.

