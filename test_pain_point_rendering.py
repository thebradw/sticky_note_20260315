#!/usr/bin/env python3
"""Tests for pain point rendering geometry within ProcessMapFlowable."""
import io
import unittest

from reportlab.pdfgen import canvas

from pdf_renderer import ProcessMapFlowable


class PainPointRenderingTests(unittest.TestCase):
    def _build_canvas(self, width=500, height=800):
        buffer = io.BytesIO()
        return canvas.Canvas(buffer, pagesize=(width, height))

    def test_pain_point_draws_to_right_of_anchor_when_space_available(self):
        sticky_notes = [
            {
                'id': 1,
                'text': 'Process Step',
                'color': 'yellow',
                'shape': 'square'
            },
            {
                'id': 2,
                'text': 'Pain point: manual handoff',
                'color': 'pink',
                'shape': 'star',
                'is_pain_point': True,
                'pain_point_for': 1
            }
        ]
        flowable = ProcessMapFlowable(sticky_notes, workflow_sequence=[1], width=500)
        flowable.canv = self._build_canvas(500, 800)
        flowable.draw()

        anchor = flowable.note_positions[1]
        pain = flowable.note_positions[2]

        self.assertGreater(pain['left'], anchor['right'])
        self.assertAlmostEqual(pain['center_y'], anchor['center_y'], delta=5)
        self.assertNotIn(2, flowable.workflow_sequence)

    def test_pain_point_moves_to_left_of_anchor_when_requested(self):
        sticky_notes = [
            {
                'id': 10,
                'text': 'Anchor near edge',
                'color': 'yellow',
                'shape': 'square'
            },
            {
                'id': 20,
                'text': 'Pain point near edge',
                'color': 'pink',
                'shape': 'cloud',
                'is_pain_point': True,
                'pain_point_for': 10
            }
        ]
        flowable = ProcessMapFlowable(sticky_notes, workflow_sequence=[10], width=500)
        flowable.canv = self._build_canvas(500, 600)
        flowable.note_positions[10] = {
            'center_x': 450,
            'center_y': 320,
            'top': 350,
            'bottom': 290,
            'left': 420,
            'right': 480,
            'width': 120,
            'height': 60
        }

        flowable.draw_single_pain_point(
            sticky_notes[1],
            flowable.note_positions[10],
            center_y=320,
            base_width=84,
            base_height=42,
            placement_side='left',
            horizontal_offset=30
        )

        pain = flowable.note_positions[20]
        self.assertLess(pain['right'], flowable.note_positions[10]['left'])
        self.assertAlmostEqual(pain['center_y'], flowable.note_positions[10]['center_y'], delta=5)


if __name__ == '__main__':
    unittest.main()
