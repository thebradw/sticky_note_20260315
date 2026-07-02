# matcher.py - Multi-photo sticky note matching system
import math
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional

class NoteMatcherSystem:
    """Handles matching sticky notes between overview and detail photos"""

    def __init__(self):
        self.grid_size = 10  # 10x10 grid for position normalization

    def normalize_position(self, note: Dict, photo_dimensions: Tuple[int, int]) -> Dict:
        """
        Convert pixel coordinates to normalized grid position (0-9 for row/col).
        Handles angled photos by using relative positioning.

        Args:
            note: Note dict with 'position' (e.g., 'top-left', 'middle-center')
            photo_dimensions: (width, height) of photo

        Returns:
            Dict with 'grid_row', 'grid_col', 'grid_cell' (e.g., 'C5')
        """
        position = note.get('position', 'middle center').lower()

        # Map position strings to grid coordinates (0-9 scale)
        # Supports both old 3x3 ("top-left") and new 5x5 ("top far-left") formats

        # Column (horizontal)
        if 'far-left' in position or 'far left' in position:
            col = 0
        elif 'far-right' in position or 'far right' in position:
            col = 9
        elif 'left' in position:
            col = 2
        elif 'right' in position:
            col = 7
        elif 'center' in position:
            col = 5
        else:
            col = 5  # default center

        # Row (vertical)
        if 'top' in position:
            row = 1
        elif 'upper-middle' in position or 'upper middle' in position:
            row = 3
        elif 'lower-middle' in position or 'lower middle' in position:
            row = 7
        elif 'bottom' in position:
            row = 9
        elif 'middle' in position:
            row = 5
        else:
            row = 5  # default middle

        # Convert to grid cell notation (A-J for columns, 0-9 for rows)
        grid_cell = f"{chr(65 + col)}{row}"

        return {
            'grid_row': row,
            'grid_col': col,
            'grid_cell': grid_cell,
            'normalized': True
        }

    def calculate_match_confidence(self, overview_note: Dict, detail_note: Dict) -> float:
        """
        Calculate match confidence score (0-100) between overview and detail notes.

        Scoring factors:
        - Color match: 20%
        - Shape match: 20%
        - Position match: 30%
        - Text anchor match: 30%

        Args:
            overview_note: Note from overview photo
            detail_note: Note from detail photo

        Returns:
            Confidence score 0-100
        """
        score = 0.0

        # Color match (20 points)
        overview_color = (overview_note.get('color') or '').lower().strip()
        detail_color = (detail_note.get('color') or '').lower().strip()

        if overview_color and detail_color:
            if overview_color == detail_color:
                score += 20
            elif self._colors_similar(overview_color, detail_color):
                score += 10  # Partial credit for similar colors

        # Shape match (20 points)
        overview_shape = (overview_note.get('shape') or '').lower().strip()
        detail_shape = (detail_note.get('shape') or '').lower().strip()

        if overview_shape and detail_shape:
            if overview_shape == detail_shape:
                score += 20
            elif self._shapes_similar(overview_shape, detail_shape):
                score += 10

        # Position match (30 points)
        overview_pos = overview_note.get('grid_position', {})
        detail_pos = detail_note.get('grid_position', {})

        if overview_pos and detail_pos:
            pos_score = self._calculate_position_similarity(overview_pos, detail_pos)
            score += pos_score * 30

        # Text anchor match (30 points)
        overview_text = (overview_note.get('text') or '').lower().strip()
        detail_text = (detail_note.get('text') or '').lower().strip()

        if overview_text and detail_text:
            text_similarity = SequenceMatcher(None, overview_text, detail_text).ratio()
            score += text_similarity * 30
        elif not overview_text and detail_text:
            # Overview had no readable text, can't use text matching
            # Redistribute text score weight to other factors
            score += 15  # Give half credit if other factors match

        return min(100.0, score)

    def _colors_similar(self, color1: str, color2: str) -> bool:
        """Check if two color names are similar (e.g., 'yellow' and 'yellowish')"""
        similar_groups = [
            {'yellow', 'yellowish', 'cream', 'beige'},
            {'pink', 'salmon', 'rose'},
            {'blue', 'light blue', 'sky blue'},
            {'green', 'light green', 'lime'},
            {'purple', 'violet', 'plum'},
            {'orange', 'peach'}
        ]

        for group in similar_groups:
            if color1 in group and color2 in group:
                return True
        return False

    def _shapes_similar(self, shape1: str, shape2: str) -> bool:
        """Check if two shapes are similar"""
        similar_groups = [
            {'square', 'rectangular', 'rectangle'},
            {'oval', 'circle', 'circular', 'ellipse'},
            {'diamond', 'rhombus'}
        ]

        for group in similar_groups:
            if shape1 in group and shape2 in group:
                return True
        return False

    def _calculate_position_similarity(self, pos1: Dict, pos2: Dict) -> float:
        """
        Calculate position similarity (0-1) using grid distance.
        Closer positions = higher score.
        """
        if not pos1.get('normalized') or not pos2.get('normalized'):
            return 0.0

        row1 = pos1.get('grid_row', 5)
        col1 = pos1.get('grid_col', 5)
        row2 = pos2.get('grid_row', 5)
        col2 = pos2.get('grid_col', 5)

        # Calculate Euclidean distance on grid
        distance = math.sqrt((row1 - row2)**2 + (col1 - col2)**2)

        # Max possible distance on 10x10 grid is sqrt(81+81) ≈ 12.7
        # Convert to similarity score (closer = higher)
        max_distance = math.sqrt(2 * (self.grid_size - 1)**2)
        similarity = 1.0 - (distance / max_distance)

        return max(0.0, min(1.0, similarity))

    def match_detail_to_overview(self, overview_notes: List[Dict], detail_notes: List[Dict]) -> Dict:
        """
        Match detail photo notes to their corresponding overview positions.

        Args:
            overview_notes: List of notes from overview photo (with grid_position)
            detail_notes: List of notes from detail photo (with grid_position)

        Returns:
            {
                'matches': [
                    {
                        'overview_note_id': int,
                        'detail_note_id': int,
                        'confidence': float,
                        'merged_note': dict
                    }
                ],
                'unmatched_overview': [note_ids],
                'unmatched_detail': [note_ids],
                'conflicts': [
                    {
                        'overview_note_id': int,
                        'detail_candidates': [
                            {'detail_note_id': int, 'confidence': float}
                        ]
                    }
                ]
            }
        """
        matches = []
        conflicts = []
        matched_overview = set()
        matched_detail = set()

        # For each detail note, find best overview match
        detail_to_overview_map = {}

        for detail_note in detail_notes:
            detail_id = detail_note.get('id')
            best_match = None
            best_confidence = 0

            for overview_note in overview_notes:
                overview_id = overview_note.get('id')
                confidence = self.calculate_match_confidence(overview_note, detail_note)

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = overview_id

            if best_match and best_confidence >= 50:  # Minimum threshold
                if best_match not in detail_to_overview_map:
                    detail_to_overview_map[best_match] = []
                detail_to_overview_map[best_match].append({
                    'detail_note_id': detail_id,
                    'confidence': best_confidence,
                    'detail_note': detail_note
                })

        # Process matches and detect conflicts
        for overview_note in overview_notes:
            overview_id = overview_note.get('id')

            if overview_id in detail_to_overview_map:
                candidates = detail_to_overview_map[overview_id]

                if len(candidates) == 1:
                    # Single match - clean
                    detail_match = candidates[0]
                    matches.append({
                        'overview_note_id': overview_id,
                        'detail_note_id': detail_match['detail_note_id'],
                        'confidence': detail_match['confidence'],
                        'merged_note': self._merge_notes(overview_note, detail_match['detail_note'])
                    })
                    matched_overview.add(overview_id)
                    matched_detail.add(detail_match['detail_note_id'])
                else:
                    # Multiple detail notes claim same overview position
                    # Check if this is a real conflict (different text) or just overlap (same text)

                    # Sort by confidence (highest first)
                    sorted_candidates = sorted(candidates, key=lambda x: x['confidence'], reverse=True)

                    # Get text from all candidates
                    texts = [c['detail_note'].get('text', '').lower().strip() for c in sorted_candidates]

                    # Check text similarity between all pairs
                    is_real_conflict = False
                    for i in range(len(texts)):
                        for j in range(i + 1, len(texts)):
                            if texts[i] and texts[j]:
                                similarity = SequenceMatcher(None, texts[i], texts[j]).ratio()
                                # If text differs by more than 20% (similarity < 0.8), it's a real conflict
                                if similarity < 0.8:
                                    is_real_conflict = True
                                    break
                        if is_real_conflict:
                            break

                    if is_real_conflict:
                        # Real conflict - different transcriptions
                        conflicts.append({
                            'overview_note_id': overview_id,
                            'detail_candidates': [
                                {
                                    'detail_note_id': c['detail_note_id'],
                                    'confidence': c['confidence'],
                                    'text': c['detail_note'].get('text', '')
                                }
                                for c in sorted_candidates
                            ]
                        })
                    else:
                        # False conflict - same text, just overlapping photos
                        # Auto-merge using highest confidence candidate
                        best_match = sorted_candidates[0]
                        matches.append({
                            'overview_note_id': overview_id,
                            'detail_note_id': best_match['detail_note_id'],
                            'confidence': best_match['confidence'],
                            'merged_note': self._merge_notes(overview_note, best_match['detail_note'])
                        })
                        matched_overview.add(overview_id)
                        matched_detail.add(best_match['detail_note_id'])

                        # Mark other candidates as matched too (they're duplicates)
                        for c in sorted_candidates[1:]:
                            matched_detail.add(c['detail_note_id'])

        # Find unmatched notes
        unmatched_overview = [n['id'] for n in overview_notes if n['id'] not in matched_overview]
        unmatched_detail = [n['id'] for n in detail_notes if n['id'] not in matched_detail]

        return {
            'matches': matches,
            'unmatched_overview': unmatched_overview,
            'unmatched_detail': unmatched_detail,
            'conflicts': conflicts
        }

    def _merge_notes(self, overview_note: Dict, detail_note: Dict) -> Dict:
        """
        Merge overview and detail note data, preferring detail for text content.

        Args:
            overview_note: Note from overview photo
            detail_note: Note from detail photo

        Returns:
            Merged note dict
        """
        merged = {
            'id': overview_note.get('id'),  # Keep overview ID for sequencing
            'text': detail_note.get('text', overview_note.get('text', '')),  # Prefer detail text
            'color': detail_note.get('color', overview_note.get('color', '')),
            'shape': detail_note.get('shape', overview_note.get('shape', '')),
            'position': overview_note.get('position', ''),  # Keep overview position
            'grid_position': overview_note.get('grid_position', {}),
            'source': 'merged',
            'detail_note_id': detail_note.get('id')
        }
        return merged

    # ------------------------------------------------------------------ #
    #  T4.0 — geometric matching (primary path for registered notes)     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _bbox_center(bbox: List[float]) -> Tuple[float, float]:
        return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2

    def _attribute_agreement(self, overview_note: Dict, detail_note: Dict) -> int:
        """Tie-breaker score: +1 per agreeing attribute (color, shape).

        Used ONLY to break near-ties in geometric matching — never as a
        primary matching signal (text is payload, position is geometry).
        """
        score = 0
        o_color = (overview_note.get('color') or '').lower().strip()
        d_color = (detail_note.get('color') or '').lower().strip()
        if o_color and d_color and (o_color == d_color
                                    or self._colors_similar(o_color, d_color)):
            score += 1
        o_shape = (overview_note.get('shape') or '').lower().strip()
        d_shape = (detail_note.get('shape') or '').lower().strip()
        if o_shape and d_shape and (o_shape == d_shape
                                    or self._shapes_similar(o_shape, d_shape)):
            score += 1
        return score

    def _merge_notes_geometric(self, overview_note: Dict,
                               detail_note: Dict) -> Dict:
        """Merge a registered detail note onto its overview position.

        Rule (T4.0): keep the overview id and overview-space bbox (the
        overview supplies position); take text, color, and shape from the
        detail note (the higher-resolution observation). Confidence scales
        with registration quality: min(99, 60 + inlier_ratio * 40).
        """
        inlier_ratio = detail_note.get('registration_inlier_ratio', 0.0)
        detail_text = (detail_note.get('text') or '').strip()
        merged = {
            'id': overview_note.get('id'),
            'bbox': list(overview_note.get('bbox', [])),
            'text': detail_text or overview_note.get('text', ''),
            'color': detail_note.get('color', overview_note.get('color', '')),
            'shape': detail_note.get('shape', overview_note.get('shape', '')),
            'position': overview_note.get('position', ''),
            'grid_position': overview_note.get('grid_position', {}),
            'source': 'registered',
            'confidence': min(99, 60 + inlier_ratio * 40),
            'detail_note_id': detail_note.get('id')
        }
        return merged

    def match_by_geometry(self, overview_notes: List[Dict],
                          detail_notes_transformed: List[Dict],
                          max_dist: float) -> Dict:
        """
        Match registered detail notes to overview notes by distance in
        overview pixel space (T4.0 primary path).

        detail_notes_transformed carry 'overview_bbox' (their bbox projected
        into overview space via the registration homography). Assignment is
        greedy one-to-one by ascending center-to-center distance; a pair is
        accepted only when distance <= max_dist. Color/shape are used ONLY
        as tie-breakers when two candidate overview notes are within 15%
        distance of each other. Text is never a matching signal.

        Returns the same schema as match_detail_to_overview:
        matches / unmatched_overview / unmatched_detail / conflicts
        (conflicts will normally be empty on this path).
        """
        overview_by_id = {}
        overview_centers = {}
        for note in overview_notes:
            bbox = note.get('bbox')
            if not bbox or len(bbox) < 4:
                continue
            overview_by_id[note['id']] = note
            overview_centers[note['id']] = self._bbox_center(bbox)

        # Candidate distances per detail note, nearest first
        candidates = {}  # detail_id -> [(dist, overview_id), ...]
        detail_by_id = {}
        for detail_note in detail_notes_transformed:
            bbox = detail_note.get('overview_bbox')
            if not bbox or len(bbox) < 4:
                continue
            detail_by_id[detail_note['id']] = detail_note
            dx, dy = self._bbox_center(bbox)
            pairs = []
            for overview_id, (ox, oy) in overview_centers.items():
                dist = math.hypot(dx - ox, dy - oy)
                if dist <= max_dist:
                    pairs.append((dist, overview_id))
            pairs.sort()
            if pairs:
                candidates[detail_note['id']] = pairs

        matches = []
        matched_overview = set()
        matched_detail = set()

        # Greedy: process detail notes in order of their nearest candidate
        order = sorted(candidates.items(), key=lambda kv: kv[1][0][0])
        for detail_id, pairs in order:
            if detail_id in matched_detail:
                continue
            available = [(d, oid) for d, oid in pairs
                         if oid not in matched_overview]
            if not available:
                continue

            best_dist, best_overview_id = available[0]
            detail_note = detail_by_id[detail_id]

            # Tie-breaker: among candidates within 15% of the nearest
            # distance, prefer the one agreeing on color/shape.
            near_ties = [(d, oid) for d, oid in available
                         if d <= best_dist * 1.15]
            if len(near_ties) > 1:
                best_dist, best_overview_id = max(
                    near_ties,
                    key=lambda pair: (
                        self._attribute_agreement(overview_by_id[pair[1]],
                                                  detail_note),
                        -pair[0]
                    )
                )

            overview_note = overview_by_id[best_overview_id]
            merged = self._merge_notes_geometric(overview_note, detail_note)
            matches.append({
                'overview_note_id': best_overview_id,
                'detail_note_id': detail_id,
                'confidence': merged['confidence'],
                'distance': round(best_dist, 1),
                'merged_note': merged
            })
            matched_overview.add(best_overview_id)
            matched_detail.add(detail_id)

        unmatched_overview = [n['id'] for n in overview_notes
                              if n['id'] not in matched_overview]
        unmatched_detail = [n['id'] for n in detail_notes_transformed
                            if n['id'] not in matched_detail]

        return {
            'matches': matches,
            'unmatched_overview': unmatched_overview,
            'unmatched_detail': unmatched_detail,
            'conflicts': []
        }

    def detect_swim_lanes(self, notes: List[Dict]) -> List[Dict]:
        """
        Detect swim lanes (horizontal workflow groupings) in the workflow.
        Detection signal: Larger rectangular notes are swim lane headers.

        Args:
            notes: List of all notes with position and shape info

        Returns:
            List of swim lane groups:
            [
                {
                    'header': note_dict,
                    'header_id': int,
                    'notes': [note_ids in this lane],
                    'row_range': (min_row, max_row)
                }
            ]
        """
        swim_lanes = []

        # Find rectangular notes (potential headers)
        headers = []
        for note in notes:
            shape = (note.get('shape') or '').lower().strip()
            if shape in ('rectangle', 'rectangular'):
                headers.append(note)

        # If only 1 rectangular note found, it's likely a title, not swim lanes
        # Need at least 2 headers to constitute swim lanes
        if len(headers) < 2:
            print(f"Swim lane detection: Found {len(headers)} rectangular note(s) - need at least 2 for swim lanes")
            return []

        # Sort headers by vertical position (top to bottom)
        headers.sort(key=lambda n: n.get('grid_position', {}).get('grid_row', 5))

        # Group notes under each header
        for i, header in enumerate(headers):
            header_row = header.get('grid_position', {}).get('grid_row', 5)

            # Determine row range for this swim lane
            # From current header row to next header row (or bottom)
            if i < len(headers) - 1:
                next_header_row = headers[i + 1].get('grid_position', {}).get('grid_row', 10)
                max_row = next_header_row - 1
            else:
                max_row = 9  # Bottom of grid

            # Find all notes in this row range (excluding headers)
            lane_notes = []
            for note in notes:
                if note['id'] == header['id']:
                    continue  # Skip the header itself

                note_row = note.get('grid_position', {}).get('grid_row', 5)
                note_shape = (note.get('shape') or '').lower().strip()

                # Check if note is in this lane and not a header itself
                if header_row <= note_row <= max_row and note_shape not in ('rectangle', 'rectangular'):
                    lane_notes.append(note['id'])

            if lane_notes:  # Only add lanes that have notes
                swim_lanes.append({
                    'header': header,
                    'header_id': header['id'],
                    'notes': lane_notes,
                    'row_range': (header_row, max_row)
                })

        return swim_lanes

    def resolve_conflict(self, conflict: Dict, chosen_detail_note_id: int) -> Dict:
        """
        Manually resolve a conflict by choosing which detail note to use.

        Args:
            conflict: Conflict dict from match_detail_to_overview
            chosen_detail_note_id: ID of the detail note to keep

        Returns:
            Resolved match dict
        """
        overview_id = conflict['overview_note_id']

        for candidate in conflict['detail_candidates']:
            if candidate['detail_note_id'] == chosen_detail_note_id:
                return {
                    'overview_note_id': overview_id,
                    'detail_note_id': chosen_detail_note_id,
                    'confidence': candidate['confidence'],
                    'resolved': True
                }

        return None


# Helper function for testing
if __name__ == "__main__":
    matcher = NoteMatcherSystem()

    # Test normalize_position
    test_note = {'position': 'top-left', 'text': 'Test'}
    normalized = matcher.normalize_position(test_note, (1920, 1080))
    print(f"Normalized position: {normalized}")

    # Test matching
    overview_notes = [
        {
            'id': 1,
            'text': 'Start',
            'color': 'green',
            'shape': 'square',
            'position': 'top-left',
            'grid_position': {'grid_row': 1, 'grid_col': 1, 'grid_cell': 'B1', 'normalized': True}
        },
        {
            'id': 2,
            'text': 'Process',
            'color': 'yellow',
            'shape': 'rectangle',
            'position': 'middle-center',
            'grid_position': {'grid_row': 5, 'grid_col': 5, 'grid_cell': 'F5', 'normalized': True}
        }
    ]

    detail_notes = [
        {
            'id': 101,
            'text': 'Start the workflow',
            'color': 'green',
            'shape': 'square',
            'position': 'top-left',
            'grid_position': {'grid_row': 1, 'grid_col': 1, 'grid_cell': 'B1', 'normalized': True}
        }
    ]

    result = matcher.match_detail_to_overview(overview_notes, detail_notes)
    print(f"\nMatching results:")
    print(f"Matches: {len(result['matches'])}")
    print(f"Conflicts: {len(result['conflicts'])}")
    print(f"Unmatched overview: {result['unmatched_overview']}")
    print(f"Unmatched detail: {result['unmatched_detail']}")
