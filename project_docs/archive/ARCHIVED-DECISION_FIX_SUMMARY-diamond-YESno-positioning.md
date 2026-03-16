# Decision Diamond Fix - YES/NO Branch Swap

## Problem Identified
In your PDF, the decision diamond "Mat'l Test req?" had:
- YES arrow pointing DOWN (crossing over the NO branch)
- NO arrow pointing RIGHT

This was **backwards** from the expected flow where:
- YES should go RIGHT (horizontal branch)
- NO should go DOWN (continues main flow)

## Root Cause
The original code positioned:
- YES branch in the main column (below diamond)
- NO branch in the right column (to the right of diamond)

But standard flowchart convention (and your physical sticky note layout) uses:
- YES → RIGHT (conditional branch)
- NO → DOWN (main flow continues)

## Changes Made

### 1. Branch Positioning (lines 723-734)
**Before:**
```python
yes_branch_y = diamond_y - note_height - 5  # Below diamond
yes_x = main_x  # Main column

no_branch_y = diamond_y + diamond_height/2 - note_height/2  # Right side
no_column_center = ...  # Right column
```

**After:**
```python
yes_branch_y = diamond_y + diamond_height/2 - note_height/2  # Right side
yes_column_center = ...  # Right column

no_branch_y = diamond_y - note_height - 5  # Below diamond
no_x = main_x  # Main column
```

### 2. Branch Drawing Logic (lines 742-802)
- Swapped YES and NO branch drawing sections
- YES now draws in right column with horizontal positioning
- NO now draws in main column continuing downward

### 3. Arrow Drawing Functions

**draw_decision_arrows() - lines 1044-1089:**
- YES arrow: Changed from DOWN to RIGHT
- NO arrow: Changed from RIGHT to DOWN
- Updated arrowhead directions and label positions

**draw_decision_arrows_to_steps() - lines 1091-1165:**
- YES: Start from right point of diamond, arrow points right
- NO: Start from bottom point of diamond, arrow points down
- Updated target position calculations

**draw_deferred_decision_arrows() - lines 1194-1251:**
- YES: Uses diamond's `right` point, draws horizontal arrow
- NO: Uses diamond's `bottom` point, draws vertical arrow

### 4. Diamond Geometry Fix (Still Active)
The earlier fix for diamond position tracking (lines 875-903) is still in place:
- Diamond shapes track actual tip positions
- Not bounding box edges
- Enables accurate arrow routing

## Expected Result

After these changes, decision diamonds will render as:

```
        [Step Above]
             |
             v
        [Decision?]
             |              YES
             | NO      -----------> [YES Branch Step]
             v
        [NO Branch Step]
             |
             v
        [Continue Flow]
```

## Testing
1. Restart Flask: `python app.py`
2. Upload `newspaper_1header_decision.jpeg`
3. Analyze and generate PDF
4. Verify:
   - YES arrow points RIGHT from diamond
   - NO arrow points DOWN from diamond
   - No crossing arrows
   - Labels positioned correctly

## Files Updated
- `app.py` - All decision diamond rendering logic corrected
