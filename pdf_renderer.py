# Auto-generated from app.py ProcessMapFlowable definition
from reportlab.lib import colors
from reportlab.platypus.flowables import Flowable
from reportlab.lib.units import inch

class ProcessMapFlowable(Flowable):
    """Visual workflow diagram with sticky notes and arrows"""
    def __init__(self, sticky_notes, workflow_sequence, width=7*inch, lane_label=None):
        Flowable.__init__(self)
        self.sticky_notes = sticky_notes
        self.workflow_sequence = workflow_sequence
        self.width = width
        self.lane_label = lane_label          # T3.0: Tier-2 lane header label
        # Track geometry for precise arrow connections
        self.note_positions = {}
        self.deferred_decision_arrows = []
        self.branch_rendered_steps = set()
        # Fixed height calculation to prevent issues
        self.height = self.calculate_fixed_height()

    def wrap(self, availWidth, availHeight):
        """Required method for ReportLab Flowable"""
        return (self.width, self.height)

    def calculate_fixed_height(self):
        """Calculate a safe fixed height"""
        if not self.workflow_sequence:
            return 200
        # Tighter calculation: 85 points per note (60 for note + 25 for arrow) + margins
        note_count = len(self.workflow_sequence)
        base = max(400, note_count * 85 + 150)
        # T3.0: add room for lane label header (11pt font + 8pt gap + buffer)
        if self.lane_label:
            base += 30
        return base

    def get_note_fill_color(self, note):
        """Map analyzer color strings to ReportLab colors"""
        color_map = {
            'pink': colors.pink,
            'yellow': colors.yellow,
            'yellowish': colors.yellow,
            'blue': colors.lightblue,
            'green': colors.lightgreen,
            'orange': colors.orange,
            'purple': colors.plum,
            'red': colors.salmon
        }
        return color_map.get((note.get('color') or '').lower(), colors.lightgreen)

    def draw_note(self, x, y, note_width, note_height, note, lines):
        """Draw a single sticky note with proper shapes"""
        fill_color = self.get_note_fill_color(note)

        # Set colors
        self.canv.setFillColor(fill_color)
        self.canv.setStrokeColor(colors.black)
        self.canv.setLineWidth(1)

        shape = note.get('shape', '').lower()

        # Draw shape
        if 'oval' in shape or 'circle' in shape:
            self.canv.ellipse(x, y, x + note_width, y + note_height, fill=1, stroke=1)
        elif 'diamond' in shape:
            # Diamond shape with bottom tip anchored at y
            path = self.canv.beginPath()
            path.moveTo(x + note_width/2, y)               # Bottom
            path.lineTo(x + note_width, y + note_height/2)  # Right
            path.lineTo(x + note_width/2, y + note_height)  # Top
            path.lineTo(x, y + note_height/2)              # Left
            path.close()
            self.canv.drawPath(path, fill=1, stroke=1)
        else:
            # Rectangle (default)
            self.canv.rect(x, y, note_width, note_height, fill=1, stroke=1)

        # Draw text
        self.canv.setFillColor(colors.black)
        self.canv.setFont("Helvetica", 9)

        # Center text
        total_text_height = len(lines) * 12
        start_y = y + note_height/2 + total_text_height/2 - 6

        for j, line in enumerate(lines):
            text_y = start_y - (j * 12)
            line_width = self.canv.stringWidth(line, "Helvetica", 9)
            self.canv.drawString(x + note_width/2 - line_width/2, text_y, line)

    def draw_arrow(self, x1, y1, x2, y2):
        """Draw arrow between notes with appropriate arrowhead direction"""
        self.canv.setStrokeColor(colors.blue)
        self.canv.setLineWidth(2)
        self.canv.line(x1, y1, x2, y2)

        # Determine arrow direction and draw appropriate arrowhead
        dx = x2 - x1
        dy = y2 - y1

        self.canv.setFillColor(colors.blue)
        path = self.canv.beginPath()

        # Horizontal arrow (left-pointing arrowhead)
        if abs(dy) < 5 and dx < 0:  # Moving left
            path.moveTo(x2, y2)
            path.lineTo(x2 + 10, y2 - 5)
            path.lineTo(x2 + 10, y2 + 5)
        # Horizontal arrow (right-pointing arrowhead)
        elif abs(dy) < 5 and dx > 0:  # Moving right
            path.moveTo(x2, y2)
            path.lineTo(x2 - 10, y2 - 5)
            path.lineTo(x2 - 10, y2 + 5)
        # Vertical arrow (default downward-pointing arrowhead)
        else:
            path.moveTo(x2, y2)
            path.lineTo(x2 - 5, y2 + 10)
            path.lineTo(x2 + 5, y2 + 10)

        path.close()
        self.canv.drawPath(path, fill=1, stroke=0)

    def wrap_text(self, text, max_width=18):
        """Wrap text for sticky notes"""
        if not text:
            return ["Empty"]
        words = str(text).split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line + " " + word) <= max_width:
                current_line += (" " if current_line else "") + word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        return lines if lines else ["Empty"]

    def is_rectangle_shape(self, note):
        """Return True when the note should behave like a header rectangle"""
        shape = (note.get('shape') or '').strip().lower()
        return shape in ('rectangle', 'rectangular')


    def draw(self):
        """Draw the complete workflow diagram with decision branch support"""
        if not self.workflow_sequence or not self.sticky_notes:
            return

        self.note_positions.clear()
        self.deferred_decision_arrows.clear()
        self.branch_rendered_steps.clear()

        notes_dict = {note['id']: note for note in self.sticky_notes}

        # Layout parameters
        margin = 50
        note_width = 120
        note_height = 60
        arrow_length = 25
        decision_branch_spacing = 200  # Horizontal space for decision branches

        # Build decision flow map
        decision_flows = self.build_decision_flows(notes_dict)

        # Start drawing from top
        current_y = self.height - margin - note_height
        main_x = self.width / 2  # Center column for main flow

        # T3.0: Render lane label above first note if set
        if self.lane_label:
            self.canv.setFont("Helvetica-Bold", 11)
            self.canv.setFillColor(colors.black)
            label_width = self.canv.stringWidth(self.lane_label, "Helvetica-Bold", 11)
            # Position: 8pt above the top of where the first note will be drawn
            label_y = current_y + note_height + 8
            self.canv.drawString(self.width / 2 - label_width / 2, label_y, self.lane_label)
            # Push notes down so they don't overlap the label (11pt font + 8pt gap)
            current_y -= (11 + 8)

        # Track which steps have been drawn to avoid duplicates
        drawn_steps = set()

        # Process each step in sequence
        i = 0
        while i < len(self.workflow_sequence):
            step_id = self.workflow_sequence[i]

            if step_id in drawn_steps:
                i += 1
                continue

            if step_id not in notes_dict:
                i += 1
                continue

            note = notes_dict[step_id]

            # Check if this is a decision diamond
            if note.get('shape') == 'diamond' and note.get('decision_branches'):
                current_y = self.draw_decision_flow(step_id, note, notes_dict, decision_flows,
                                                  main_x, current_y, note_width, note_height,
                                                  arrow_length, decision_branch_spacing, drawn_steps)

                # If no NO-branch target was defined, queue a deferred downward
                # continuation arrow from the diamond's bottom tip to the next
                # undrawn sequential step.  Deferred so it renders on top of all
                # note fills, preventing the arrowhead from being hidden behind
                # the following note's box.
                branches = note.get('decision_branches', {}) or {}
                if not branches.get('no_next_step'):
                    for j in range(i + 1, len(self.workflow_sequence)):
                        next_id = self.workflow_sequence[j]
                        if next_id not in drawn_steps and next_id in notes_dict:
                            self._queue_deferred_arrow(
                                step_id, 'continuation', next_id, '', arrow_length)
                            break
            else:
                # Draw regular step
                current_y = self.draw_regular_step(step_id, note, main_x, current_y,
                                                 note_width, note_height, arrow_length, drawn_steps, i)

            i += 1

        self.draw_deferred_decision_arrows()
        self.draw_deferred_rejoin_arrows()
        self.draw_pain_points(note_width, note_height)

    def build_decision_flows(self, notes_dict):
        """Build a map of decision flows to understand branching structure"""
        decision_flows = {}

        for note_id, note in notes_dict.items():
            if note.get('shape') == 'diamond' and note.get('decision_branches'):
                branches = note.get('decision_branches')
                decision_flows[note_id] = {
                    'yes_branch': [],
                    'no_branch': [],
                    'yes_target': branches.get('yes_next_step'),
                    'no_target': branches.get('no_next_step'),
                    'rejoin': branches.get('rejoin_step')
                }

                # Find all steps in each branch until rejoin
                if branches.get('rejoin_step'):
                    rejoin_index = None
                    yes_index = None
                    no_index = None

                    try:
                        if branches.get('rejoin_step') in self.workflow_sequence:
                            rejoin_index = self.workflow_sequence.index(branches.get('rejoin_step'))
                        if branches.get('yes_next_step') in self.workflow_sequence:
                            yes_index = self.workflow_sequence.index(branches.get('yes_next_step'))
                        if branches.get('no_next_step') in self.workflow_sequence:
                            no_index = self.workflow_sequence.index(branches.get('no_next_step'))

                        # Build branch sequences - each branch gets only its own steps
                        if yes_index is not None and rejoin_index is not None:
                            # YES branch: from yes_next_step up to (but not including) no_next_step or rejoin
                            if no_index is not None:
                                # Stop before NO branch starts
                                decision_flows[note_id]['yes_branch'] = self.workflow_sequence[yes_index:no_index]
                            else:
                                # No NO branch, go all the way to rejoin
                                decision_flows[note_id]['yes_branch'] = self.workflow_sequence[yes_index:rejoin_index]

                        if no_index is not None and rejoin_index is not None:
                            # NO branch: from no_next_step to rejoin (no overlap with YES)
                            decision_flows[note_id]['no_branch'] = self.workflow_sequence[no_index:rejoin_index]

                    except ValueError:
                        pass  # Handle case where steps not found in sequence

        return decision_flows

    def draw_decision_flow(self, diamond_id, diamond_note, notes_dict, decision_flows,
                         main_x, current_y, note_width, note_height, arrow_length, branch_spacing, drawn_steps):
        """Draw a decision diamond and its branches"""

        # Draw the diamond in main column
        diamond_y = current_y
        diamond_width, diamond_height = self.draw_single_note(diamond_id, diamond_note, main_x, diamond_y,
                                                             note_width, note_height)
        drawn_steps.add(diamond_id)

        # Store diamond position for later arrow drawing
        diamond_x = main_x - diamond_width/2
        diamond_right = diamond_x + diamond_width

        branches = diamond_note.get('decision_branches', {})
        flow = decision_flows.get(diamond_id, {})

        # Position for branches
        # YES branch: to the RIGHT of diamond (horizontal branch)
        # Position vertically centered with diamond, with proper horizontal gap
        yes_branch_y = diamond_y + diamond_height/2 - note_height/2  # Center align with diamond
        base_yes_center = max(
            main_x + branch_spacing,
            diamond_right + arrow_length + note_width/2 + 20  # arrow_length provides gap
        )
        yes_column_center = base_yes_center

        # NO branch: positioned BELOW diamond (continues main flow)
        # Use same arrow_length spacing as normal box-to-box
        no_branch_y = diamond_y - note_height - arrow_length  # Consistent spacing
        no_x = main_x  # No branch stays in main column

        # Store first step positions for accurate arrow drawing
        first_yes_pos = None
        first_no_pos = None
        last_yes_step_id = None
        last_no_step_id = None

        # Draw Yes branch (right column - horizontal from diamond)
        yes_bottom_y = yes_branch_y
        if flow.get('yes_branch'):
            for i, step_id in enumerate(flow['yes_branch']):
                if step_id in notes_dict and step_id not in drawn_steps:
                    note = notes_dict[step_id]
                    lines = self.wrap_text(note.get('text', 'No text'))
                    max_line_length = max((len(line) for line in lines), default=0)
                    estimated_width = max(note_width, max_line_length * 8 + 20)
                    required_center = diamond_right + arrow_length + 10 + estimated_width / 2
                    max_center = self.width - estimated_width / 2 - 40
                    yes_column_center = max(yes_column_center, required_center)
                    yes_column_center = min(yes_column_center, max_center)

                    step_width, step_height = self.draw_single_note(step_id, note, yes_column_center, yes_bottom_y,
                                                      note_width, note_height)
                    drawn_steps.add(step_id)
                    self.branch_rendered_steps.add(step_id)
                    last_yes_step_id = step_id

                    pos = self.note_positions.get(step_id)
                    if i == 0 and pos:
                        first_yes_pos = (pos['left'], pos['center_y'])

                    yes_bottom_y -= (step_height + arrow_length)
                    # Draw connecting arrow between steps in yes branch
                    if i > 0:  # Not the first step
                        prev_id = flow['yes_branch'][i - 1]
                        prev_note = notes_dict.get(prev_id, {})
                        prev_pos = self.note_positions.get(prev_id)
                        curr_pos = pos
                        if prev_pos and curr_pos and not self.is_rectangle_shape(prev_note):
                            column_x = prev_pos['center_x']
                            self.draw_arrow(column_x, prev_pos['bottom'], column_x, curr_pos['top'])

        # Draw No branch (main column - continues downward flow)
        no_bottom_y = no_branch_y
        if flow.get('no_branch'):
            for i, step_id in enumerate(flow['no_branch']):
                if step_id in notes_dict and step_id not in drawn_steps:
                    note = notes_dict[step_id]
                    step_width, step_height = self.draw_single_note(step_id, note, no_x, no_bottom_y,
                                                       note_width, note_height)
                    drawn_steps.add(step_id)
                    self.branch_rendered_steps.add(step_id)
                    last_no_step_id = step_id

                    pos = self.note_positions.get(step_id)
                    if i == 0 and pos:
                        first_no_pos = (pos['center_x'], pos['top'])

                    no_bottom_y -= (step_height + arrow_length)
                    # Draw connecting arrow between steps in no branch
                    if i > 0:  # Not the first step
                        prev_id = flow['no_branch'][i - 1]
                        prev_note = notes_dict.get(prev_id, {})
                        prev_pos = self.note_positions.get(prev_id)
                        curr_pos = pos
                        if prev_pos and curr_pos and not self.is_rectangle_shape(prev_note):
                            column_x = prev_pos['center_x']
                            self.draw_arrow(column_x, prev_pos['bottom'], column_x, curr_pos['top'])

        # Draw rejoin arrows if needed
        if flow.get('rejoin'):
            rejoin_y = min(yes_bottom_y, no_bottom_y) - arrow_length
            yes_rejoin_drawn = False
            no_rejoin_drawn = False

            print(f"\n=== REJOIN ARROW DEBUG ===")
            print(f"Diamond: {diamond_note.get('text', '?')[:20]}")
            print(f"Rejoin step ID: {flow.get('rejoin')}")
            print(f"Calculated rejoin_y: {rejoin_y:.1f}")
            print(f"yes_bottom_y: {yes_bottom_y:.1f}, no_bottom_y: {no_bottom_y:.1f}")

            if flow.get('yes_branch') and last_yes_step_id:
                yes_note = notes_dict.get(last_yes_step_id, {})
                yes_pos = self.note_positions.get(last_yes_step_id)
                if yes_pos and not self.is_rectangle_shape(yes_note):
                    column_x = yes_pos['center_x']
                    print(f"Drawing YES vertical arrow: from ({column_x:.1f}, {yes_pos['bottom']:.1f}) to ({column_x:.1f}, {rejoin_y:.1f})")
                    self.draw_arrow(column_x, yes_pos['bottom'], column_x, rejoin_y)
                    yes_rejoin_drawn = True

            if flow.get('no_branch') and last_no_step_id:
                no_note = notes_dict.get(last_no_step_id, {})
                no_pos = self.note_positions.get(last_no_step_id)
                if no_pos and not self.is_rectangle_shape(no_note):
                    column_x = no_pos['center_x']
                    print(f"Drawing NO vertical arrow: from ({column_x:.1f}, {no_pos['bottom']:.1f}) to ({column_x:.1f}, {rejoin_y:.1f})")
                    self.draw_arrow(column_x, no_pos['bottom'], column_x, rejoin_y)
                    no_rejoin_drawn = True

            if no_rejoin_drawn:
                no_pos = self.note_positions.get(last_no_step_id)
                yes_pos = self.note_positions.get(last_yes_step_id) if last_yes_step_id else None
                start_x = no_pos['center_x'] if no_pos else main_x
                end_x = yes_pos['center_x'] if yes_pos else yes_column_center
                print(f"Drawing NO-rejoin horizontal: from ({start_x:.1f}, {rejoin_y:.1f}) to ({end_x:.1f}, {rejoin_y:.1f})")
                self.draw_arrow(start_x, rejoin_y, end_x, rejoin_y)

            # Draw horizontal connector from YES to rejoin step (when YES rejoins at NO)
            if yes_rejoin_drawn and last_yes_step_id:
                rejoin_step_id = flow.get('rejoin')
                rejoin_pos = self.note_positions.get(rejoin_step_id)
                yes_pos = self.note_positions.get(last_yes_step_id)

                print(f"\nChecking for YESâ†’rejoin horizontal connector:")
                print(f"  last_yes_step_id: {last_yes_step_id}")
                print(f"  rejoin_step_id: {rejoin_step_id}")
                print(f"  yes_pos: {yes_pos}")
                print(f"  rejoin_pos: {rejoin_pos}")

                if yes_pos:  # We have YES position, queue the arrow for later
                    # Queue this arrow to be drawn after rejoin step is positioned
                    if not hasattr(self, 'deferred_rejoin_arrows'):
                        self.deferred_rejoin_arrows = []

                    self.deferred_rejoin_arrows.append({
                        'yes_step_id': last_yes_step_id,
                        'rejoin_step_id': rejoin_step_id,
                        'rejoin_y': rejoin_y
                    })
                    print(f"  âœ“ Queued rejoin arrow for later drawing")
                else:
                    print(f"  âœ— Missing YES position data")
            else:
                print(f"\nSkipped YESâ†’rejoin check: yes_rejoin_drawn={yes_rejoin_drawn}, last_yes_step_id={last_yes_step_id}")

            print(f"=== END REJOIN DEBUG ===\n")

            # Draw decision arrows AFTER all steps are positioned (so arrows appear on top)
            self.draw_decision_arrows_to_steps(diamond_x, diamond_y, diamond_width, diamond_height,
                                             diamond_note, arrow_length, first_yes_pos, first_no_pos)

            return rejoin_y - arrow_length
        else:
            # Draw decision arrows AFTER all steps are positioned (so arrows appear on top)
            self.draw_decision_arrows_to_steps(diamond_x, diamond_y, diamond_width, diamond_height,
                                             diamond_note, arrow_length, first_yes_pos, first_no_pos)

            return min(yes_bottom_y, no_bottom_y)

    def draw_regular_step(self, step_id, note, x, y, note_width, note_height, arrow_length, drawn_steps, step_index):
        """Draw a regular (non-decision) step"""
        width, height = self.draw_single_note(step_id, note, x, y, note_width, note_height)
        drawn_steps.add(step_id)
        is_rectangle_step = self.is_rectangle_shape(note)

        # Check if this step is part of a decision branch (skip automatic arrows for branch steps)
        is_branch_step = step_id in self.branch_rendered_steps

        # Queue a deferred arrow to the next sequential step so the arrowhead is
        # rendered AFTER all note fills.  This prevents the arrowhead from being
        # painted over by the next note's background box when the next note is
        # taller than the current one (a common occurrence with multi-line notes).
        if step_index < len(self.workflow_sequence) - 1 and not is_branch_step and not is_rectangle_step:
            next_step_id = self.workflow_sequence[step_index + 1]
            self._queue_deferred_arrow(step_id, 'regular', next_step_id, '', arrow_length)

        # Use 2× arrow_length as the inter-note gap so that when the next note is
        # taller than the current one (e.g. 95 px vs 65 px) the arrow still has
        # enough vertical room to be fully visible.
        return y - height - arrow_length * 2

    def draw_single_note(self, step_id, note, center_x, y, default_width, default_height):
        """Draw a single note and return its actual dimensions"""
        text = note.get('text', 'No text')
        lines = self.wrap_text(text)

        # Calculate actual dimensions
        actual_width = max(default_width, len(max(lines, key=len)) * 8 + 20)
        actual_height = max(default_height, len(lines) * 15 + 20)

        # Center the note
        x = center_x - actual_width/2

        # Draw the note
        self.draw_note(x, y, actual_width, actual_height, note, lines)

        # Record geometry for precise arrow routing
        # Diamond shapes have different anchor points than rectangles
        if note.get('shape') == 'diamond':
            # For diamonds: y is the bottom TIP, geometry is different
            # Diamond path: bottom(y) -> right -> top(y+height) -> left -> close
            self.note_positions[step_id] = {
                'center_x': center_x,
                'center_y': y + actual_height / 2,
                'top': y + actual_height,      # Top tip
                'bottom': y,                   # Bottom tip
                'left': x,                     # Left point (at center height)
                'right': x + actual_width,     # Right point (at center height)
                'width': actual_width,
                'height': actual_height
            }
        else:
            # Rectangle/oval/other shapes use standard bounding box
            self.note_positions[step_id] = {
                'center_x': center_x,
                'center_y': y + actual_height / 2,
                'top': y + actual_height,
                'bottom': y,
                'left': center_x - actual_width / 2,
                'right': center_x + actual_width / 2,
                'width': actual_width,
                'height': actual_height
            }

        return actual_width, actual_height

    def draw_pain_points(self, base_note_width, base_note_height):
                """Render pain point callouts next to their associated workflow steps"""
                pain_points = [n for n in self.sticky_notes if n.get('is_pain_point')]
                if not pain_points:
                    return

                anchor_groups = {}
                for note in pain_points:
                    anchor_groups.setdefault(note.get('pain_point_for'), []).append(note)

                default_width = base_note_width * 0.7
                default_height = base_note_height * 0.7
                vertical_gap = 8
                horizontal_offset = 30

                for anchor_id, group in anchor_groups.items():
                    anchor_pos = self.note_positions.get(anchor_id)
                    if not anchor_pos:
                        continue

                    group.sort(key=lambda n: n.get('center_y', 0), reverse=True)

                    desired_center_x = anchor_pos['right'] + horizontal_offset + default_width / 2
                    max_right = self.width - 40
                    placement_side = 'right'
                    if desired_center_x + default_width / 2 > max_right:
                        placement_side = 'left'

                    if not group:
                        continue

                    total_span = (len(group) - 1) * (default_height + vertical_gap)
                    start_center_y = anchor_pos['center_y'] + total_span / 2

                    for idx, pain_note in enumerate(group):
                        center_y = start_center_y - idx * (default_height + vertical_gap)
                        self.draw_single_pain_point(
                            pain_note,
                            anchor_pos,
                            center_y,
                            default_width,
                            default_height,
                            placement_side,
                            horizontal_offset
                        )



    def draw_single_pain_point(self, note, anchor_pos, center_y, base_width, base_height, placement_side, horizontal_offset):
                """Draw a single pain point with oval shape, dashed border, and smaller text"""
                text = note.get('text', 'Pain point') or 'Pain point'
                lines = self.wrap_text(text, max_width=22)

                longest_line = max((len(line) for line in lines), default=0)
                actual_width = max(base_width, longest_line * 6.5 + 20)
                actual_height = max(base_height, len(lines) * 12 + 14)

                if placement_side == 'left':
                    center_x = anchor_pos['left'] - horizontal_offset - actual_width / 2
                else:
                    center_x = anchor_pos['right'] + horizontal_offset + actual_width / 2

                margin = 20
                min_center_x = margin + actual_width / 2
                max_center_x = self.width - margin - actual_width / 2

                if placement_side == 'right':
                    min_required = anchor_pos['right'] + 5 + actual_width / 2
                    min_center_x = max(min_center_x, min_required)
                else:
                    max_required = anchor_pos['left'] - 5 - actual_width / 2
                    max_center_x = min(max_center_x, max_required)

                center_x = max(min(center_x, max_center_x), min_center_x)

                x = center_x - actual_width / 2
                y = center_y - actual_height / 2

                fill_color = self.get_note_fill_color(note)

                self.canv.saveState()
                dash_length = 3
                dash_gap = 2
                self.canv.setDash(dash_length, dash_gap)
                self.canv.setStrokeColor(colors.black)
                self.canv.setLineWidth(1)
                set_alpha = getattr(self.canv, 'setFillAlpha', None)
                if callable(set_alpha):
                    set_alpha(0.6)
                self.canv.setFillColor(fill_color)
                self.canv.ellipse(x, y, x + actual_width, y + actual_height, fill=1, stroke=1)
                if callable(set_alpha):
                    set_alpha(1)
                self.canv.setDash()
                self.canv.setFillColor(colors.black)
                self.canv.setFont("Helvetica", 7)

                total_text_height = len(lines) * 10
                start_y = y + actual_height/2 + total_text_height/2 - 5
                for i, line in enumerate(lines):
                    text_y = start_y - i * 10
                    line_width = self.canv.stringWidth(line, "Helvetica", 7)
                    self.canv.drawString(x + actual_width/2 - line_width/2, text_y, line)

                self.canv.restoreState()

                self.note_positions[note['id']] = {
                    'center_x': center_x,
                    'center_y': center_y,
                    'top': y + actual_height,
                    'bottom': y,
                    'left': x,
                    'right': x + actual_width,
                    'width': actual_width,
                    'height': actual_height
                }



    def identify_parallel_groups(self):
        """Identify groups of parallel processes"""
        notes_dict = {note['id']: note for note in self.sticky_notes}
        parallel_groups = {}

        for i, note_id in enumerate(self.workflow_sequence):
            step_number = i + 1
            note = notes_dict.get(note_id, {})
            parallel_with = note.get('parallel_with')

            if parallel_with:
                # Find which step number the parallel_with corresponds to
                try:
                    parallel_step_index = self.workflow_sequence.index(parallel_with)
                    parallel_step_number = parallel_step_index + 1

                    # Add to existing group or create new group
                    if parallel_step_number not in parallel_groups:
                        parallel_groups[parallel_step_number] = [
                            {'step': parallel_step_number, 'note_id': parallel_with}
                        ]
                    parallel_groups[parallel_step_number].append(
                        {'step': step_number, 'note_id': note_id}
                    )
                except ValueError:
                    pass  # parallel_with note not found in sequence

        return parallel_groups

    def draw_parallel_group(self, parallel_steps, notes_dict, y_pos, spacing, 
                          note_width, note_height, arrow_length):
        """Draw a group of parallel processes"""
        num_parallel = len(parallel_steps)

        # Calculate positions for parallel boxes
        total_width = (num_parallel - 1) * spacing
        start_x = (self.width - total_width) / 2

        box_positions = []

        for i, step_info in enumerate(parallel_steps):
            note_id = step_info['note_id']
            note = notes_dict.get(note_id, {})
            text = note.get('text', 'No text')
            lines = self.wrap_text(text)

            # Calculate note dimensions
            actual_width = max(note_width, len(max(lines, key=len)) * 8 + 20)
            actual_height = max(note_height, len(lines) * 15 + 20)

            # Position horizontally
            x = start_x + (i * spacing) - (actual_width / 2)
            y = y_pos

            # Draw the note
            self.draw_note(x, y, actual_width, actual_height, note, lines)
            box_positions.append((x + actual_width/2, y, actual_width, actual_height))

        # Draw merge arrow at bottom
        if box_positions:
            self.draw_merge_arrow(box_positions, arrow_length)

    def draw_split_arrow(self, center_x, start_y, num_branches, arrow_length):
        """Draw arrow that splits into multiple branches"""
        # Draw main line down
        main_end_y = start_y - arrow_length // 2
        self.canv.setStrokeColor(colors.blue)
        self.canv.setLineWidth(2)
        self.canv.line(center_x, start_y, center_x, main_end_y)

        # Draw horizontal line
        branch_spacing = 150
        total_width = (num_branches - 1) * branch_spacing
        left_x = center_x - total_width / 2
        right_x = center_x + total_width / 2
        self.canv.line(left_x, main_end_y, right_x, main_end_y)

        # Draw arrows to each branch
        for i in range(num_branches):
            branch_x = left_x + (i * branch_spacing)
            branch_end_y = main_end_y - arrow_length // 2
            self.canv.line(branch_x, main_end_y, branch_x, branch_end_y)

            # Draw arrowhead
            self.canv.setFillColor(colors.blue)
            path = self.canv.beginPath()
            path.moveTo(branch_x, branch_end_y)
            path.lineTo(branch_x - 5, branch_end_y + 10)
            path.lineTo(branch_x + 5, branch_end_y + 10)
            path.close()
            self.canv.drawPath(path, fill=1, stroke=0)

    def draw_merge_arrow(self, box_positions, arrow_length):
        """Draw arrows from parallel boxes that merge into one"""
        if not box_positions:
            return

        # Find the lowest point of all boxes
        min_y = min(pos[1] for pos in box_positions)
        merge_y = min_y - arrow_length // 2

        # Calculate center point for merge
        avg_x = sum(pos[0] for pos in box_positions) / len(box_positions)

        self.canv.setStrokeColor(colors.blue)
        self.canv.setLineWidth(2)

        # Draw lines from each box down to merge point
        for center_x, y, width, height in box_positions:
            # Line from bottom of box to merge level
            self.canv.line(center_x, y, center_x, merge_y)
            # Horizontal line to center
            self.canv.line(center_x, merge_y, avg_x, merge_y)

        # Draw final arrow down from merge point
        final_end_y = merge_y - arrow_length // 2
        self.canv.line(avg_x, merge_y, avg_x, final_end_y)

        # Draw arrowhead
        self.canv.setFillColor(colors.blue)
        path = self.canv.beginPath()
        path.moveTo(avg_x, final_end_y)
        path.lineTo(avg_x - 5, final_end_y + 10)
        path.lineTo(avg_x + 5, final_end_y + 10)
        path.close()
        self.canv.drawPath(path, fill=1, stroke=0)

    def draw_decision_arrows(self, x, y, width, height, note, notes_dict, arrow_length):
        """Draw decision arrows from diamond shapes"""
        branches = note.get('decision_branches', {})
        yes_step = branches.get('yes_next_step')
        no_step = branches.get('no_next_step')
        yes_label = branches.get('yes_label', 'Yes')
        no_label = branches.get('no_label', 'No')

        center_x = x + width / 2
        center_y = y + height / 2
        bottom_y = y

        # Draw Yes arrow (to the RIGHT - horizontal branch)
        if yes_step:
            self.canv.setStrokeColor(colors.blue)
            self.canv.setLineWidth(2)
            right_x = x + width
            end_x = right_x + arrow_length
            self.canv.line(right_x, center_y, end_x, center_y)

            # Draw arrowhead
            self.canv.setFillColor(colors.blue)
            path = self.canv.beginPath()
            path.moveTo(end_x, center_y)
            path.lineTo(end_x - 10, center_y - 5)
            path.lineTo(end_x - 10, center_y + 5)
            path.close()
            self.canv.drawPath(path, fill=1, stroke=0)

            # Add Yes label
            self.canv.setFillColor(colors.black)
            self.canv.setFont("Helvetica", 8)
            label_x = right_x + 8
            label_y = center_y + 8
            self.canv.drawString(label_x, label_y, yes_label)

        # Draw No arrow (straight DOWN - continues main flow)
        if no_step:
            self.canv.setStrokeColor(colors.blue)
            self.canv.setLineWidth(2)
            end_y = bottom_y - arrow_length
            self.canv.line(center_x, bottom_y, center_x, end_y)

            # Draw arrowhead
            self.canv.setFillColor(colors.blue)
            path = self.canv.beginPath()
            path.moveTo(center_x, end_y)
            path.lineTo(center_x - 5, end_y + 10)
            path.lineTo(center_x + 5, end_y + 10)
            path.close()
            self.canv.drawPath(path, fill=1, stroke=0)

            # Add No label
            self.canv.setFillColor(colors.black)
            self.canv.setFont("Helvetica", 8)
            label_x = center_x + 8
            label_y = center_y - 10
            self.canv.drawString(label_x, label_y, no_label)

    def draw_decision_arrows_to_steps(self, x, y, width, height, note, arrow_length, yes_pos, no_pos):
        """Draw decision arrows from diamond to actual step positions"""
        branches = note.get('decision_branches', {}) or {}
        yes_label = branches.get('yes_label', 'Yes')
        no_label = branches.get('no_label', 'No')
        diamond_id = note.get('id')

        # YES arrow starts from RIGHT point of diamond (horizontal)
        start_yes_x = x + width
        start_yes_y = y + height / 2

        # NO arrow starts from BOTTOM point of diamond (vertical)
        start_no_x = x + width / 2
        start_no_y = y

        yes_target_id = branches.get('yes_next_step')
        no_target_id = branches.get('no_next_step')

        def draw_yes_arrow(target_x, target_y):
            """YES arrow goes RIGHT (horizontal)"""
            self.canv.setStrokeColor(colors.blue)
            self.canv.setLineWidth(2)
            self.canv.line(start_yes_x, start_yes_y, target_x, target_y)

            self.canv.setFillColor(colors.blue)
            path = self.canv.beginPath()
            path.moveTo(target_x, target_y)
            path.lineTo(target_x - 10, target_y - 5)
            path.lineTo(target_x - 10, target_y + 5)
            path.close()
            self.canv.drawPath(path, fill=1, stroke=0)

            self.canv.setFillColor(colors.black)
            self.canv.setFont('Helvetica', 8)
            label_x = (start_yes_x + target_x) / 2
            label_y = start_yes_y + 8
            self.canv.drawString(label_x, label_y, yes_label)

        def draw_no_arrow(target_x, target_y):
            """NO arrow goes DOWN (vertical)"""
            self.canv.setStrokeColor(colors.blue)
            self.canv.setLineWidth(2)
            self.canv.line(start_no_x, start_no_y, target_x, target_y)

            self.canv.setFillColor(colors.blue)
            path = self.canv.beginPath()
            path.moveTo(target_x, target_y)
            path.lineTo(target_x - 5, target_y + 10)
            path.lineTo(target_x + 5, target_y + 10)
            path.close()
            self.canv.drawPath(path, fill=1, stroke=0)

            self.canv.setFillColor(colors.black)
            self.canv.setFont('Helvetica', 8)
            label_x = start_no_x + 8
            label_y = (start_no_y + target_y) / 2
            self.canv.drawString(label_x, label_y, no_label)

        if yes_pos:
            draw_yes_arrow(*yes_pos)
        elif yes_target_id:
            target_pos = self.note_positions.get(yes_target_id)
            if target_pos:
                draw_yes_arrow(target_pos['left'], target_pos['center_y'])
            else:
                self._queue_deferred_arrow(diamond_id, 'yes', yes_target_id, yes_label, arrow_length)

        if no_pos:
            draw_no_arrow(*no_pos)
        elif no_target_id:
            target_pos = self.note_positions.get(no_target_id)
            if target_pos:
                draw_no_arrow(target_pos['center_x'], target_pos['top'])
            else:
                self._queue_deferred_arrow(diamond_id, 'no', no_target_id, no_label, arrow_length)


    def _queue_deferred_arrow(self, diamond_id, branch, target_id, label, arrow_length):
        if not diamond_id or not target_id:
            return

        for existing in self.deferred_decision_arrows:
            if existing['diamond_id'] == diamond_id and existing['branch'] == branch:
                return

        self.deferred_decision_arrows.append({
            'diamond_id': diamond_id,
            'branch': branch,
            'target_id': target_id,
            'label': label,
            'arrow_length': arrow_length
        })

    def draw_deferred_decision_arrows(self):
        for arrow in self.deferred_decision_arrows:
            diamond_pos = self.note_positions.get(arrow['diamond_id'])
            if not diamond_pos:
                continue

            branch = arrow['branch']
            label = arrow['label']
            arrow_length = arrow.get('arrow_length', 25)

            if branch == 'yes':
                # YES arrow goes RIGHT (horizontal)
                start_x = diamond_pos['right']
                start_y = diamond_pos['center_y']
                target_pos = self.note_positions.get(arrow['target_id'])
                if target_pos:
                    end_x = target_pos['left']
                    end_y = target_pos['center_y']
                else:
                    end_x = start_x + arrow_length
                    end_y = start_y

                self.canv.setStrokeColor(colors.blue)
                self.canv.setLineWidth(2)
                self.canv.line(start_x, start_y, end_x, end_y)

                self.canv.setFillColor(colors.blue)
                path = self.canv.beginPath()
                path.moveTo(end_x, end_y)
                path.lineTo(end_x - 10, end_y - 5)
                path.lineTo(end_x - 10, end_y + 5)
                path.close()
                self.canv.drawPath(path, fill=1, stroke=0)

                self.canv.setFillColor(colors.black)
                self.canv.setFont('Helvetica', 8)
                label_x = (start_x + end_x) / 2
                label_y = start_y + 8
                self.canv.drawString(label_x, label_y, label)
            elif branch == 'no':
                # NO arrow goes DOWN (vertical)
                start_x = diamond_pos['center_x']
                start_y = diamond_pos['bottom']
                target_pos = self.note_positions.get(arrow['target_id'])
                if target_pos:
                    end_x = target_pos['center_x']
                    end_y = target_pos['top']
                else:
                    end_x = start_x
                    end_y = start_y - arrow_length

                self.canv.setStrokeColor(colors.blue)
                self.canv.setLineWidth(2)
                self.canv.line(start_x, start_y, end_x, end_y)

                self.canv.setFillColor(colors.blue)
                path = self.canv.beginPath()
                path.moveTo(end_x, end_y)
                path.lineTo(end_x - 5, end_y + 10)
                path.lineTo(end_x + 5, end_y + 10)
                path.close()
                self.canv.drawPath(path, fill=1, stroke=0)

                self.canv.setFillColor(colors.black)
                self.canv.setFont('Helvetica', 8)
                label_x = start_x + 8
                label_y = (start_y + end_y) / 2
                label_y = start_y + 8
                self.canv.drawString(label_x, label_y, label)

            elif branch == 'regular':
                # Plain downward step-to-step arrow anchored to actual note_positions
                # so the arrowhead always touches the top of the next note exactly,
                # regardless of how tall either note turned out to be after text-wrap.
                source_pos = self.note_positions.get(arrow['diamond_id'])  # source step id
                target_pos = self.note_positions.get(arrow['target_id'])
                if source_pos and target_pos:
                    start_x = source_pos['center_x']
                    start_y = source_pos['bottom']
                    end_x = target_pos['center_x']
                    end_y = target_pos['top']
                    self.canv.setStrokeColor(colors.black)
                    self.canv.setLineWidth(1.5)
                    self.canv.line(start_x, start_y, end_x, end_y)
                    self.canv.setFillColor(colors.black)
                    path = self.canv.beginPath()
                    path.moveTo(end_x, end_y)           # arrowhead tip at note top
                    path.lineTo(end_x - 5, end_y + 10)  # body above the note
                    path.lineTo(end_x + 5, end_y + 10)
                    path.close()
                    self.canv.drawPath(path, fill=1, stroke=0)

            elif branch == 'continuation':
                # Plain downward continuation from diamond bottom to next sequential
                # step — drawn deferred so it appears on top of note fills.
                # No label: this is not a decision branch, just the main flow path.
                start_x = diamond_pos['center_x']
                start_y = diamond_pos['bottom']
                target_pos = self.note_positions.get(arrow['target_id'])
                if target_pos:
                    # Anchor to the actual rendered top of the next note, not the
                    # estimated position — this eliminates the gap caused by notes
                    # whose actual height differs from the default note_height.
                    end_x = target_pos['center_x']
                    end_y = target_pos['top']
                else:
                    end_x = start_x
                    end_y = start_y - arrow_length

                self.canv.setStrokeColor(colors.blue)
                self.canv.setLineWidth(2)
                self.canv.line(start_x, start_y, end_x, end_y)

                self.canv.setFillColor(colors.blue)
                path = self.canv.beginPath()
                path.moveTo(end_x, end_y)           # arrowhead tip at note top
                path.lineTo(end_x - 5, end_y + 10)  # body is in the gap above
                path.lineTo(end_x + 5, end_y + 10)
                path.close()
                self.canv.drawPath(path, fill=1, stroke=0)

        self.deferred_decision_arrows.clear()

    def draw_deferred_rejoin_arrows(self):
        """Draw horizontal rejoin arrows after all steps are positioned"""
        if not hasattr(self, 'deferred_rejoin_arrows'):
            return

        print(f"\n=== DRAWING DEFERRED REJOIN ARROWS ===")
        print(f"Queued rejoin arrows: {len(self.deferred_rejoin_arrows)}")

        for arrow_data in self.deferred_rejoin_arrows:
            yes_step_id = arrow_data['yes_step_id']
            rejoin_step_id = arrow_data['rejoin_step_id']
            rejoin_y = arrow_data['rejoin_y']

            yes_pos = self.note_positions.get(yes_step_id)
            rejoin_pos = self.note_positions.get(rejoin_step_id)

            print(f"\nProcessing rejoin arrow:")
            print(f"  YES step {yes_step_id}: {yes_pos}")
            print(f"  Rejoin step {rejoin_step_id}: {rejoin_pos}")

            if yes_pos and rejoin_pos:
                yes_x = yes_pos['center_x']
                rejoin_x = rejoin_pos['right']  # Use right edge, not center

                print(f"  yes_x: {yes_x:.1f}, rejoin_x (right edge): {rejoin_x:.1f}")
                print(f"  Column difference: {abs(yes_x - rejoin_x):.1f}px")

                # Only draw if columns are different
                if abs(yes_x - rejoin_x) > 20:
                    print(f"  âœ“ Drawing horizontal: ({yes_x:.1f}, {rejoin_y:.1f}) â†’ ({rejoin_x:.1f}, {rejoin_y:.1f})")
                    self.draw_arrow(yes_x, rejoin_y, rejoin_x, rejoin_y)
                else:
                    print(f"  âœ— Skipped - same column")
            else:
                print(f"  âœ— Still missing position data")

        print(f"=== END DEFERRED REJOIN ARROWS ===\n")
        self.deferred_rejoin_arrows.clear()





