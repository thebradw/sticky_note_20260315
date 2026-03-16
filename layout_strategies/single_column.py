from .base import WorkflowLayoutStrategy


class SingleColumnStrategy(WorkflowLayoutStrategy):
    """Default layout: single vertical workflow."""

    name = 'single-column'

    def sort_workflow(self, workflow_notes, img_width, img_height):
        workflow_notes.sort(key=lambda n: n.get('center_y', 0))
        for note in workflow_notes:
            self._flag_pain_point(note)

        standard_notes = [n for n in workflow_notes if not n.get('is_pain_point')]
        pain_notes = [n for n in workflow_notes if n.get('is_pain_point')]
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
            pains.sort(key=lambda n: n.get('center_y', 0))

        return mapping

    def _find_anchor(self, pain_note, standard_notes):
        return self._closest_note(pain_note, standard_notes)

    def _closest_note(self, pain_note, candidates):
        best = None
        best_distance = self.pain_point_vertical_threshold
        for candidate in candidates or []:
            distance = abs(pain_note.get('center_y', 0) - candidate.get('center_y', 0))
            if distance < best_distance:
                best = candidate
                best_distance = distance
        return best

