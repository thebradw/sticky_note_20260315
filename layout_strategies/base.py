class WorkflowLayoutStrategy:
    """Base strategy for grouping and sorting sticky notes by layout."""

    name = 'base'
    standard_shapes = {'square', 'rectangular', 'diamond'}
    pain_point_vertical_threshold = 200

    def group_workflows(self, notes, img_width, img_height):
        """Return a list of workflows (each workflow is a list of note dicts)."""
        return [notes]


    def _flag_pain_point(self, note):
        """Mark a note as a pain point when its shape is non-standard."""
        shape = (note.get('shape') or '').lower()
        if shape and shape not in self.standard_shapes:
            note['is_pain_point'] = True
            note['parallel_with'] = None
            note.pop('decision_branches', None)
            note['arrows_to'] = note.get('arrows_to', [])
            return True
        note.pop('is_pain_point', None)
        return False

    def sort_workflow(self, workflow_notes, img_width, img_height):
        """Sort notes within a workflow. Default: top-to-bottom order."""
        workflow_notes.sort(key=lambda n: n.get('center_y', 0))
        for note in workflow_notes:
            self._flag_pain_point(note)

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name}>"
