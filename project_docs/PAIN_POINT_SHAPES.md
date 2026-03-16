# Pain Point Shape Handling - Clarification Update

## Key Change

**Pain points are identified by ANY non-standard shape, not just ovals/circles.  Do not use color to identify pain points.**

## Shape Classification

### Standard Workflow Shapes
These participate in the workflow and get arrows:
- `square` - Regular process step
- `rectangular` - Headers, labels, swim lane markers
- `diamond` - Decision points (Yes/No branches)

### Pain Point Shapes (Non-Standard)
These are annotations and do NOT get arrows:
- `star` ⭐
- `oval` / `circle` ⭕
- `cloud` ☁️
- `callout` 💭
- `arrow` ➡️
- `hexagon` ⬡
- Any other shape not in the standard list

## Detection Logic

```python
# Define standard workflow shapes
standard_shapes = ['square', 'rectangular', 'diamond']

if shape not in standard_shapes:
    # Any non-standard shape is a pain point
    note['is_pain_point'] = True
```

## PDF Rendering

**Important**: Regardless of the original shape detected by Claude Vision:
- All pain points are rendered as **ovals** in the PDF
- This provides visual consistency
- The original shape (star, cloud, etc.) is preserved in the data but not rendered

### Why Render as Ovals?

1. **Simplicity** - Easier to implement one rendering path
2. **Consistency** - All pain points look the same in output
3. **Clarity** - Ovals clearly distinguish pain points from workflow steps
4. **Shape Info Preserved** - Original shape is still in the JSON data if needed

## Visual Distinction

Pain points in PDF are distinguished by:
- ✓ Oval shape (always)
- ✓ Smaller size (70% of normal)
- ✓ Dashed border (not solid)
- ✓ Semi-transparent fill (60% opacity)
- ✓ Offset position (30px to right of associated step)
- ✓ Smaller font (7pt vs 9pt)
- ✓ NO arrows connecting to/from them

## Real-World Examples

From actual workflow sessions:

### Pink Star ⭐
```
Original: Star shape, pink color
Text: "input errors"
Detection: is_pain_point = True
PDF Rendering: Pink oval with dashed border
```

### Red Cloud ☁️
```
Original: Cloud shape, red color  
Text: "Phantom Demand"
Detection: is_pain_point = True
PDF Rendering: Red oval with dashed border
```

### Orange Callout 💭
```
Original: Callout shape, orange color
Text: "If fails do manually"
Detection: is_pain_point = True
PDF Rendering: Orange oval with dashed border
```

## Test Coverage

Unit test validates:
- Star shape → detected as pain point ✓
- Cloud shape → detected as pain point ✓
- Pain points excluded from parallel detection ✓
- Pain points excluded from workflow sequencing ✓

## User Instructions

When conducting process mapping sessions:
1. Use **any non-square, non-rectangular, non-diamond shape** for pain points
2. Common choices: stars (most visible), clouds, ovals
3. Color can be anything 
4. Tool will automatically detect and handle them correctly
5. They'll appear as ovals in the final PDF regardless of original shape

## Data Structure

Pain points retain full metadata:
```json
{
  "id": 4,
  "text": "input errors",
  "color": "pink",
  "shape": "star",        // Original shape preserved
  "is_pain_point": true,  // Flagged for special handling
  "bbox": [150, 450, 220, 510],
  "center_x": 185,
  "center_y": 480
}
```

## Benefits

✅ **Flexible** - Any non-standard shape works  
✅ **Future-proof** - New shapes automatically handled  
✅ **Clear logic** - Simple rule: standard vs non-standard  
✅ **Consistent output** - All pain points look the same in PDF  
✅ **Data preserved** - Original shape info retained for future features


