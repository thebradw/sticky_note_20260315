from .base import WorkflowLayoutStrategy


class HorizontalSwimLaneStrategy(WorkflowLayoutStrategy):
    """Each horizontal lane is its own workflow, sorted left-to-right."""

    name = 'horizontal-swim-lanes'

    def group_workflows(self, notes, img_width, img_height):
        if not notes:
            return []

        # --- Pre-flag pain points so they don't pollute gap detection ---
        for note in notes:
            self._flag_pain_point(note)

        standard_notes = [n for n in notes if not n.get('is_pain_point')]
        pain_notes = [n for n in notes if n.get('is_pain_point')]

        if not standard_notes:
            # Degenerate: everything is a pain point
            return [notes]

        sorted_standard = sorted(standard_notes,
                                 key=lambda n: n.get('center_y', 0))

        # Adaptive threshold — tuned for horizontal rows where pain points
        # have already been removed, leaving cleaner inter-lane gaps.
        threshold = max(40, min(90, (img_height or 750) * 0.08))
        print(f"  Horizontal lane gap threshold: {threshold:.0f} px "
              f"(img_height={img_height})")

        # --- Gap-based lane detection on standard notes only ---
        lanes = [[sorted_standard[0]]]
        for note in sorted_standard[1:]:
            previous = lanes[-1][-1]
            gap = note.get('center_y', 0) - previous.get('center_y', 0)
            if gap > threshold:
                lanes.append([note])
            else:
                lanes[-1].append(note)

        # --- Re-assign pain points to the nearest lane by center_y ---
        for pain in pain_notes:
            py = pain.get('center_y', 0)
            best_lane = 0
            best_dist = float('inf')
            for idx, lane in enumerate(lanes):
                # Compare against the median Y of the lane
                lane_ys = [n.get('center_y', 0) for n in lane]
                lane_mid = sorted(lane_ys)[len(lane_ys) // 2]
                dist = abs(py - lane_mid)
                if dist < best_dist:
                    best_dist = dist
                    best_lane = idx
            lanes[best_lane].append(pain)

        print(f"  Grouped into {len(lanes)} horizontal lanes "
              f"({len(pain_notes)} pain point(s) re-assigned)")
        return lanes

    def sort_workflow(self, workflow_notes, img_width, img_height):
        workflow_notes.sort(key=lambda n: n.get('center_x', 0))

        # Pain points were already flagged in group_workflows, but flag
        # again for safety (e.g. if called standalone).
        for note in workflow_notes:
            self._flag_pain_point(note)

        standard_notes = [n for n in workflow_notes
                          if not n.get('is_pain_point')]
        pain_notes = [n for n in workflow_notes
                      if n.get('is_pain_point')]
        pain_map = self._attach_pain_points(standard_notes, pain_notes)

        ordered = []
        for note in standard_notes:
            ordered.append(note)
            for pain in pain_map.get(id(note), []):
                ordered.append(pain)

        ordered.extend(pain_map.get(None, []))
        workflow_notes[:] = ordered

    def _attach_pain_points(self, standard_notes, pain_notes):
        mapping = {None: []}
        if not standard_notes:
            mapping[None].extend(pain_notes)
            return mapping

        for pain in pain_notes:
            anchor = self._find_anchor(pain, standard_notes)
            if anchor:
                pain['pain_point_for'] = anchor['id']
                mapping.setdefault(id(anchor), []).append(pain)
            else:
                pain.pop('pain_point_for', None)
                mapping[None].append(pain)

        for pains in mapping.values():
            pains.sort(key=lambda n: n.get('center_x', 0))

        return mapping

    def _find_anchor(self, pain_note, standard_notes):
        """Find nearest process step using weighted X + Y distance.

        In horizontal lanes pain points sit below their anchor step,
        roughly aligned by X.  X-distance is the primary axis but we
        also factor in Y so a note in the same row wins over a
        header/step far away vertically.
        """
        best = None
        best_score = float('inf')
        px = pain_note.get('center_x', 0)
        py = pain_note.get('center_y', 0)

        for candidate in standard_notes:
            cx = candidate.get('center_x', 0)
            cy = candidate.get('center_y', 0)
            dx = abs(px - cx)
            dy = abs(py - cy)
            # Weight X 1.0, Y 0.5 — X alignment matters most but Y
            # breaks ties (prefer the step directly above over one
            # far away at the same X).
            score = dx + 0.5 * dy
            if score < best_score:
                best_score = score
                best = candidate

        # Apply a generous max distance to avoid wild matches
        if best_score > self.pain_point_vertical_threshold:
            return None
        return best
