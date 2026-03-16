# Decision Branch Overlap Fix

## Root Cause Found

The NO branch was appearing to the right because **step 13 was being included in BOTH branches**:

```
yes_branch: [12, 13]  ← WRONG - includes step 13
no_branch: [13]       ← Correct
```

This happened because `build_decision_flows()` used Python slice notation without considering overlap:
```python
yes_branch = sequence[yes_index:rejoin_index]  # [11:13] = [12, 13]
no_branch = sequence[no_index:rejoin_index]    # [12:13] = [13]
```

Since step 13 was in the YES branch list, it got drawn in the right column alongside step 12. Then when the NO branch tried to draw, step 13 was already in `drawn_steps`, so it was skipped.

## The Fix

Modified `build_decision_flows()` (lines 695-705) to build exclusive branch lists:

```python
# YES branch: stops BEFORE NO branch starts
if no_index is not None:
    yes_branch = sequence[yes_index:no_index]  # [11:12] = [12] only
else:
    yes_branch = sequence[yes_index:rejoin_index]

# NO branch: from NO start to rejoin (no overlap)
no_branch = sequence[no_index:rejoin_index]  # [12:13] = [13] only
```

Now each branch gets only its own steps:
- YES branch: [12] - "Mat Lab req" goes RIGHT
- NO branch: [13] - "Test Input Review" goes DOWN (centered)

## Expected Result

After this fix:
```
        [Lab Testing]
             |
             v
      [Mat Cert req?]
             |                  YES
             | NO          -----------> [Mat Lab req]
             v
    [Test Input Review]
             |
             v
    [Final Inspection]
```

## All Fixes Applied

1. ✅ Diamond geometry tracking (lines 883-895)
2. ✅ YES/NO branch swap (lines 723-802)  
3. ✅ Arrow direction swap (lines 1044-1089, 1091-1165, 1194-1251)
4. ✅ **Branch overlap fix** (lines 695-705) ← NEW

## Testing

Replace app.py and test with newspaper_1header_decision.jpeg:
1. "Mat Lab req" should appear to the RIGHT of diamond
2. "Test Input Review" should appear BELOW and CENTERED under diamond
3. No overlapping or duplicate rendering
