from .base import WorkflowLayoutStrategy


class NewspaperColumnsStrategy(WorkflowLayoutStrategy):
    """Layout where a single workflow is read column-by-column."""

    name = 'newspaper'
    max_columns = 4

    def sort_workflow(self, workflow_notes, img_width, img_height):
        for note in workflow_notes:
            note['parallel_with'] = None
        columns = {}
        for note in workflow_notes:
            column_index = self._get_column_index(note, img_width)
            note['_column_index'] = column_index
            columns.setdefault(column_index, []).append(note)

        ordered_notes = []
        for column_index in sorted(columns.keys()):
            column_notes = columns[column_index]
            column_notes.sort(key=lambda n: n.get('center_y', 0))
            column_center = self._get_column_center(column_notes)
            for note in column_notes:
                self._flag_pain_point(note)

            standard_notes = [n for n in column_notes if not n.get('is_pain_point')]
            pain_notes = [n for n in column_notes if n.get('is_pain_point')]

            pain_map = self._attach_pain_points(standard_notes, pain_notes)

            for note in standard_notes:
                ordered_notes.append(note)
                for pain in pain_map.get(id(note), []):
                    ordered_notes.append(pain)

            for pain in pain_map.get(None, []):
                ordered_notes.append(pain)

        for note in workflow_notes:
            note.pop('_column_index', None)
        workflow_notes[:] = ordered_notes




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
        if not standard_notes:
            return None

        priority_shapes = ['square', 'diamond', 'rectangular']
        for shape in priority_shapes:
            candidates = [n for n in standard_notes if (n.get('shape') or '').lower() == shape]
            anchor = self._closest_note(pain_note, candidates)
            if anchor:
                return anchor

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

    def _get_column_index(self, note, img_width):
        center_x = note.get('center_x', 0)
        col_width = max(img_width / self.max_columns, 1)
        index = int(center_x / col_width)
        return max(0, min(self.max_columns - 1, index))

    def _get_column_center(self, column_notes):
        centers = [n.get('center_x', 0) for n in column_notes if (n.get('shape') or '').lower() in self.standard_shapes]
        if not centers:
            centers = [n.get('center_x', 0) for n in column_notes]
        if not centers:
            return None
        return sum(centers) / len(centers)




