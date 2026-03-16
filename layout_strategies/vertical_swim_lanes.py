from .base import WorkflowLayoutStrategy


class VerticalSwimLaneStrategy(WorkflowLayoutStrategy):
    """Each vertical lane is its own workflow, sorted top-to-bottom."""

    name = 'vertical-swim-lanes'

    def group_workflows(self, notes, img_width, img_height):
        sorted_notes = sorted(notes, key=lambda n: n.get('center_x', 0))
        if not sorted_notes:
            return []

        # Use a relative threshold — 12 % of image width, capped at 150 px.
        # 20 % was too high: on a 486 px wide image the real inter-column gap
        # was only 70 px (14 % of width), so columns were merged into one lane.
        # 12 % gives 58 px for that image, correctly splitting at 70 px.
        # Large images still cap at 150 px.
        threshold = max(50, min(150, (img_width or 750) * 0.12))
        print(f"  Vertical lane gap threshold: {threshold:.0f} px "
              f"(img_width={img_width})")

        lanes = [[sorted_notes[0]]]
        for note in sorted_notes[1:]:
            previous = lanes[-1][-1]
            gap = note.get('center_x', 0) - previous.get('center_x', 0)
            if gap > threshold:
                lanes.append([note])
            else:
                lanes[-1].append(note)

        print(f"  Grouped into {len(lanes)} vertical lanes")
        return lanes
