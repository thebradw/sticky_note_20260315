# image_analyzer.py
import os
import base64
from dotenv import load_dotenv
import anthropic
from PIL import Image
import json
import io
import re
from difflib import SequenceMatcher
from statistics import median
from matcher import NoteMatcherSystem
from layout_strategies import get_layout_strategy


def is_rectangle_shape(shape):
    """Return True if the shape string indicates a rectangle-role note.

    Includes 'square' so that square sticky notes used as lane headers or
    banners are detected correctly by classify_rectangle_roles().  The PDF
    renderer has its own separate method that governs arrow-drawing behaviour
    and should not be changed to include 'square' (regular process steps are
    also square and must still receive arrows).
    """
    return (shape or '').strip().lower() in ('rectangle', 'rectangular', 'square')

class StickyNoteAnalyzer:
    def __init__(self):
        load_dotenv(override=True)   # override=True so .env wins over empty OS env vars
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = "claude-4-sonnet-20250514"
        self.matcher = NoteMatcherSystem()
    
    def encode_image(self, image_path):
        """Convert image to base64 for Claude API"""
        try:
            # Open and potentially resize image if too large
            with Image.open(image_path) as img:
                # If image is very large, resize it
                if max(img.size) > 4000:
                    img.thumbnail((4000, 4000), Image.Resampling.LANCZOS)
                
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save to bytes
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                
                # Encode to base64
                image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                return image_data
                
        except Exception as e:
            print(f"Error processing image {image_path}: {e}")
            return None

    # -------------------------------------------------------------- #
    #  Pass-2 OCR — crop each note and re-read its text              #
    # -------------------------------------------------------------- #

    def _refine_text_with_crops(self, image_path, notes, img_width, img_height):
        """Crop each detected note from the original image and re-OCR.

        The first Vision pass sees the entire wall photo, so each note
        occupies only a tiny fraction of the frame.  This second pass
        crops each bounding-box region (with padding) from the full-res
        source, scales it up, and sends a grid of labelled crops for
        focused text reading.

        Updates ``note['text']`` in place and returns the notes list.
        """
        try:
            with Image.open(image_path) as full_img:
                orig_w, orig_h = full_img.size

                # Scale factor: Vision's coordinate space → actual pixels
                sx = orig_w / (img_width or orig_w)
                sy = orig_h / (img_height or orig_h)

                crops = []  # (note_id, PIL.Image)
                for note in notes:
                    bbox = note.get('bbox')
                    if not bbox or len(bbox) < 4:
                        continue
                    # Convert Vision coordinates to full-res pixels
                    x1 = int(bbox[0] * sx)
                    y1 = int(bbox[1] * sy)
                    x2 = int(bbox[2] * sx)
                    y2 = int(bbox[3] * sy)

                    # Add padding (15% of note size, min 20 px)
                    pad_x = max(20, int((x2 - x1) * 0.15))
                    pad_y = max(20, int((y2 - y1) * 0.15))
                    x1 = max(0, x1 - pad_x)
                    y1 = max(0, y1 - pad_y)
                    x2 = min(orig_w, x2 + pad_x)
                    y2 = min(orig_h, y2 + pad_y)

                    crop = full_img.crop((x1, y1, x2, y2))
                    # Scale up small crops so text is large enough to read
                    min_dim = 300
                    cw, ch = crop.size
                    if cw < min_dim or ch < min_dim:
                        scale = max(min_dim / cw, min_dim / ch)
                        crop = crop.resize(
                            (int(cw * scale), int(ch * scale)),
                            Image.Resampling.LANCZOS)
                    crops.append((note['id'], crop))

                if not crops:
                    return notes

                # Build grid montage — 5 crops per row
                COLS = 5
                LABEL_H = 30  # height for the ID label above each crop
                # Uniform cell size = max dimensions across all crops
                cell_w = max(c.size[0] for _, c in crops) + 4
                cell_h = max(c.size[1] for _, c in crops) + LABEL_H + 4
                rows = (len(crops) + COLS - 1) // COLS
                grid = Image.new('RGB',
                                 (cell_w * COLS, cell_h * rows),
                                 (255, 255, 255))

                from PIL import ImageDraw
                draw = ImageDraw.Draw(grid)
                for idx, (nid, crop) in enumerate(crops):
                    col = idx % COLS
                    row = idx // COLS
                    gx = col * cell_w + 2
                    gy = row * cell_h + 2
                    # Draw note ID label
                    draw.text((gx, gy), f"#{nid}", fill=(0, 0, 0))
                    grid.paste(crop, (gx, gy + LABEL_H))

                # Encode grid to JPEG
                buf = io.BytesIO()
                grid.save(buf, format='JPEG', quality=92)
                grid_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

                id_list = ', '.join(f'#{nid}' for nid, _ in crops)
                ocr_prompt = f"""You are an OCR tool. This image is a grid of cropped sticky notes
from a wall photo.  Each crop is labelled with a number (e.g. #1, #2 …).

For EVERY numbered crop, read the handwritten text EXACTLY as written.
Preserve abbreviations, acronyms, and misspellings.  If a word is truly
unreadable, write [illegible].  Do NOT paraphrase or invent text.

Return ONLY a JSON object mapping note number to its text.  Example:
{{"1": "PO for materials in Obeer", "2": "QSA - track inv & assign lot #"}}

Notes to read: {id_list}
"""
                print(f"  [OCR Pass 2] Sending {len(crops)} crops for text refinement …")
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    temperature=0,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image",
                             "source": {"type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": grid_b64}},
                            {"type": "text", "text": ocr_prompt}
                        ]
                    }]
                )

                raw = resp.content[0].text
                json_match = re.search(r'\{.*\}', raw, re.DOTALL)
                if not json_match:
                    print("  [OCR Pass 2] WARNING — could not parse JSON from response")
                    return notes

                text_map = json.loads(json_match.group())
                updated = 0
                for note in notes:
                    key = str(note['id'])
                    if key in text_map:
                        new_text = text_map[key].strip()
                        if new_text and new_text != note.get('text', ''):
                            note['text'] = new_text
                            updated += 1
                print(f"  [OCR Pass 2] Updated text on {updated}/{len(crops)} notes")

        except Exception as e:
            print(f"  [OCR Pass 2] WARNING — refinement failed: {e}")

        return notes

    def analyze_overview(self, image_path):
        """
        Analyze overview photo - extract spatial map of all sticky notes.
        Gets color, shape, approximate position, and any readable text as anchors.

        Args:
            image_path: Path to overview photo

        Returns:
            {
                'summary': str,
                'sticky_notes': [
                    {
                        'id': int,
                        'text': str (may be empty if not readable),
                        'color': str,
                        'position': str,
                        'shape': str,
                        'grid_position': dict
                    }
                ],
                'photo_dimensions': (width, height),
                'readability_score': float (0-1)
            }
        """
        print(f"Analyzing overview: {os.path.basename(image_path)}")

        image_data = self.encode_image(image_path)
        if not image_data:
            return None

        # Get photo dimensions
        with Image.open(image_path) as img:
            photo_dimensions = img.size

        prompt = """
Analyze this photo of a wall covered in sticky notes. Your job is to catalog EVERY SINGLE sticky note visible in the image - no matter how small, overlapping, or unclear.

CRITICAL INSTRUCTIONS:
- There are likely 50-150 sticky notes in this image. Do NOT stop at 20 or 30. Count and list ALL of them.
- Extract the EXACT text you can read on each note. Do NOT infer, guess, or assume what text might say based on context.
- If you cannot read the text clearly on a note, set text to "UNREADABLE" but STILL include the note with its position, color, and shape.
- Do NOT skip notes just because they are small, partially hidden, or at the edges of the image.
- Scan the ENTIRE image systematically: left-to-right, top-to-bottom. Do not stop until you have covered every area.

For each sticky note, extract:
1. Color (green, yellow, blue, pink, orange, purple, white, etc.)
2. Shape:
   * "rectangular" - wider than tall (landscape orientation, often used as headers/labels)
   * "square" - roughly equal width and height (standard sticky note)
   * "diamond" - rotated 45 degrees (decision point). Diamonds are physically standard square sticky notes that have been deliberately rotated 45 degrees so they sit on a corner point-up. If you see a square sticky note that is tilted/rotated so it rests on its corner rather than flat on its edge, classify it as "diamond" not "square". Look carefully for this rotation; it may be subtle but it is always intentional.
   * "circular" or "oval"
   * Other shapes (star, arrow, etc.)
   * Some sticky notes may be star-shaped, cloud-shaped, arrow-shaped, or other non-standard shapes. These are deliberately chosen to indicate pain points or callouts. Look carefully at the outline or silhouette of each note; if it has points, curves, or irregular edges rather than straight sides, report its actual shape (star, cloud, arrow, burst, etc.). Do not classify non-standard shapes as "square" just because they are roughly the same size as square notes. The physical outline of the note determines the shape.
3. Position using a 5x5 grid for better precision:
   - Horizontal: far-left, left, center, right, far-right
   - Vertical: top, upper-middle, middle, lower-middle, bottom
   - Combine as: "top far-left", "upper-middle center", "bottom right", etc.
4. Text content - the EXACT words you can see. Use "UNREADABLE" if unclear.

Return ONLY valid JSON with this structure:
{
    "summary": "Brief factual description of what you see on the wall (colors, layout, groupings)",
    "sticky_notes": [
        {
            "id": 1,
            "text": "exact text or UNREADABLE",
            "color": "green",
            "position": "top far-left",
            "shape": "square"
        }
    ],
    "total_notes": 100
}

FINAL CHECK: Before responding, count your sticky_notes array. If it is under 40, you have likely missed notes. Re-scan the image and add any you missed.
        """

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                temperature=0,   # deterministic — suppress text hallucination
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            response_text = message.content[0].text

            # Check if response was truncated (hit token limit)
            if message.stop_reason == 'max_tokens':
                print(f"WARNING: Response was truncated at max_tokens. Some notes may be missing.")

            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

            if json_match:
                analysis_data = json.loads(json_match.group())

                # Normalize positions to grid coordinates
                if 'sticky_notes' in analysis_data:
                    readable_count = 0
                    for note in analysis_data['sticky_notes']:
                        note['grid_position'] = self.matcher.normalize_position(note, photo_dimensions)
                        text = note.get('text', '').strip()
                        if text and text.upper() != 'UNREADABLE':
                            readable_count += 1

                    # Calculate readability score
                    total_notes = len(analysis_data['sticky_notes'])
                    analysis_data['readability_score'] = readable_count / total_notes if total_notes > 0 else 0
                    analysis_data['readable_count'] = readable_count

                analysis_data['photo_dimensions'] = photo_dimensions
                analysis_data['analysis_type'] = 'overview'

                print(f"Overview analysis complete: {len(analysis_data.get('sticky_notes', []))} notes, {analysis_data.get('readable_count', 0)} readable")
                return analysis_data
            else:
                return {"raw_analysis": response_text}

        except Exception as e:
            print(f"Overview analysis failed: {e}")
            return None

    def analyze_detail(self, image_path):
        """
        Analyze detail photo - extract full text content from close-up.

        Args:
            image_path: Path to detail photo

        Returns:
            {
                'sticky_notes': [
                    {
                        'id': int,
                        'text': str (full text),
                        'color': str,
                        'position': str (within detail frame),
                        'shape': str,
                        'grid_position': dict
                    }
                ],
                'photo_dimensions': (width, height)
            }
        """
        print(f"Analyzing detail: {os.path.basename(image_path)}")

        image_data = self.encode_image(image_path)
        if not image_data:
            return None

        # Get photo dimensions
        with Image.open(image_path) as img:
            photo_dimensions = img.size

        prompt = """
Analyze this close-up detail photo of sticky notes. This is a zoomed-in shot showing detailed text.

Extract:
1. For each sticky note visible:
   - Full text content (read carefully and completely)
   - Color
   - Shape
   - Position within this detail photo (top-left, top-center, etc.)

Return JSON:
{
    "sticky_notes": [
        {
            "id": 1,
            "text": "Complete text from sticky note",
            "color": "yellow",
            "position": "top-left",
            "shape": "square"
        }
    ]
}
        """

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0,   # deterministic — suppress text hallucination
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            response_text = message.content[0].text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

            if json_match:
                analysis_data = json.loads(json_match.group())

                # Normalize positions to grid coordinates
                if 'sticky_notes' in analysis_data:
                    for note in analysis_data['sticky_notes']:
                        note['grid_position'] = self.matcher.normalize_position(note, photo_dimensions)

                analysis_data['photo_dimensions'] = photo_dimensions
                analysis_data['analysis_type'] = 'detail'

                print(f"Detail analysis complete: {len(analysis_data.get('sticky_notes', []))} notes")
                return analysis_data
            else:
                return {"raw_analysis": response_text}

        except Exception as e:
            print(f"Detail analysis failed: {e}")
            return None

    def process_multi_photo_session(self, overview_path, detail_paths, flow_direction='single-column'):
        """
        Orchestrate multi-photo workflow: overview Ã¢â€ â€™ detail analyses Ã¢â€ â€™ matching Ã¢â€ â€™ merge.

        Args:
            overview_path: Path to overview photo
            detail_paths: List of paths to detail photos
            flow_direction: layout selector ('single-column', 'newspaper', 'horizontal-swim-lanes', 'vertical-swim-lanes')

        Returns:
            {
                'summary': str,
                'sticky_notes': [merged notes with confidence scores],
                'workflow_sequence': [note_ids],
                'matches': [match details],
                'conflicts': [conflicts requiring resolution],
                'unmatched_detail': [notes from detail photos that couldn't be matched],
                'swim_lanes': [detected swim lane groupings]
            }
        """
        print(f"Processing multi-photo session: 1 overview + {len(detail_paths)} detail photos")

        # Step 1: Analyze overview
        overview_result = self.analyze_overview(overview_path)
        if not overview_result or 'sticky_notes' not in overview_result:
            print("Overview analysis failed, falling back to single-photo workflow")
            return self.analyze_workflow(overview_path)

        overview_notes = overview_result['sticky_notes']
        print(f"Overview: {len(overview_notes)} notes detected")

        # Step 2: Check if overview is sufficient (high readability)
        readability_score = overview_result.get('readability_score', 0)
        if readability_score >= 0.8 and not detail_paths:
            print(f"Overview has {readability_score:.1%} readability - sufficient without detail photos")
            # Use overview as final result
            return {
                'summary': overview_result.get('summary', ''),
                'sticky_notes': overview_notes,
                'workflow_sequence': [n['id'] for n in overview_notes],
                'readability_sufficient': True,
                'flow_direction': flow_direction
            }

        # Step 3: Analyze detail photos
        all_detail_notes = []
        detail_results = []

        for detail_path in detail_paths:
            detail_result = self.analyze_detail(detail_path)
            if detail_result and 'sticky_notes' in detail_result:
                detail_results.append(detail_result)
                all_detail_notes.extend(detail_result['sticky_notes'])

        print(f"Detail photos: {len(all_detail_notes)} notes extracted")

        # Step 4: Match detail notes to overview positions
        if all_detail_notes:
            match_result = self.matcher.match_detail_to_overview(overview_notes, all_detail_notes)

            # Merge matched notes
            merged_notes = []
            for match in match_result['matches']:
                merged_note = match['merged_note']
                merged_note['confidence'] = match['confidence']
                merged_notes.append(merged_note)
                # Debug: Log merged note text
                print(f"Merged note ID {merged_note.get('id')}: text='{merged_note.get('text', 'NO TEXT')[:50]}...'")

            print(f"Total merged notes: {len(merged_notes)}")

            # Add unmatched overview notes (no detail available)
            for note_id in match_result['unmatched_overview']:
                overview_note = next((n for n in overview_notes if n['id'] == note_id), None)
                if overview_note:
                    overview_note['confidence'] = 50  # Low confidence - no detail match
                    overview_note['source'] = 'overview_only'
                    merged_notes.append(overview_note)

            # Collect unmatched detail notes
            unmatched_detail_notes = [
                n for n in all_detail_notes
                if n['id'] in match_result['unmatched_detail']
            ]

        else:
            # No detail photos processed
            merged_notes = overview_notes
            for note in merged_notes:
                note['confidence'] = 50
                note['source'] = 'overview_only'
            match_result = {'matches': [], 'conflicts': [], 'unmatched_detail': []}
            unmatched_detail_notes = []

        # Step 5: Sort notes based on flow direction
        if flow_direction == 'newspaper':
            # Column-by-column (left-to-right, then top-to-bottom within columns)
            def newspaper_sort(note):
                grid_pos = note.get('grid_position', {})
                col = grid_pos.get('grid_col', 5)
                row = grid_pos.get('grid_row', 5)
                return (col, row)
            merged_notes.sort(key=newspaper_sort)
        else:
            # Left-to-right (row-by-row, top-to-bottom)
            def left_right_sort(note):
                grid_pos = note.get('grid_position', {})
                row = grid_pos.get('grid_row', 5)
                col = grid_pos.get('grid_col', 5)
                return (row, col)
            merged_notes.sort(key=left_right_sort)

        # Re-assign IDs based on sorted order
        for i, note in enumerate(merged_notes):
            note['id'] = i + 1

        workflow_sequence = [note['id'] for note in merged_notes]

        # Step 6: Detect swim lanes
        swim_lanes = self.matcher.detect_swim_lanes(merged_notes)

        return {
            'summary': overview_result.get('summary', 'Multi-photo workflow'),
            'sticky_notes': merged_notes,
            'workflow_sequence': workflow_sequence,
            'matches': match_result.get('matches', []),
            'conflicts': match_result.get('conflicts', []),
            'unmatched_detail': unmatched_detail_notes,
            'swim_lanes': swim_lanes,
            'flow_direction': flow_direction,
            'readability_sufficient': False
        }

    def analyze_workflow(self, image_path, flow_direction='single-column'):
        """Analyze sticky note workflow in an image
        
        Args:
            image_path: Path to the image file
            flow_direction: Layout type - 'single-column', 'newspaper', 'horizontal-swim-lanes', 'vertical-swim-lanes'
        """
        
        print(f"Analyzing: {os.path.basename(image_path)}")
        
        # Encode the image
        image_data = self.encode_image(image_path)
        if not image_data:
            return None
        
        # Create the analysis prompt
        prompt = """
YOU ARE AN OCR TOOL.  Your #1 job is to read and transcribe the EXACT text
written on every sticky note.  Do NOT paraphrase, summarise, infer, or
generate plausible-sounding text.  Copy each word EXACTLY as it appears in
the handwriting — including misspellings, abbreviations, and acronyms.
If a word is illegible, write "[illegible]" rather than guessing.

Analyze this sticky note workflow image and provide PRECISE spatial data.

For EACH sticky note visible, provide:
1. **Bounding box coordinates** in pixels: [x_min, y_min, x_max, y_max]
   - x_min, y_min = top-left corner
   - x_max, y_max = bottom-right corner
   - Use the actual image dimensions as reference

2. **Text content** - exactly what is written

3. **Color** - green, yellow, blue, pink, orange, purple, white, etc.
   - IMPORTANT: Judge each sticky note's color relative to the OTHER sticky notes in the
     image, not relative to the wall background. A dark or vividly colored wall (red, brown,
     terracotta, green) will cast a tint on every note — compensate for this by comparing
     notes to each other. If most notes share one hue and a few are clearly a different hue,
     name them differently even if the absolute color looks ambiguous against the wall.
   - In particular: do NOT report a yellow sticky as "orange" or "salmon" simply because
     the wall behind it is warm-toned. If a note is distinctly lighter/brighter/more yellow
     than the surrounding pink/salmon notes, call it "yellow".

4. **Shape** - Be VERY specific:
   - "square" - roughly equal width and height
   - "rectangular" - wider than tall (landscape) - often used for headers
   - "diamond" - rotated 45 degrees (THIS IS A DECISION POINT). Diamonds are physically standard square sticky notes that have been deliberately rotated 45 degrees so they sit on a corner point-up. If you see a square sticky note that is tilted/rotated so it rests on its corner rather than flat on its edge, classify it as "diamond" not "square". Look carefully for this rotation; it may be subtle but it is always intentional.
   - "circle" or "oval"
   - Other shapes
   - Some sticky notes may be star-shaped, cloud-shaped, arrow-shaped, or other non-standard shapes. These are deliberately chosen to indicate pain points or callouts. Look carefully at the outline or silhouette of each note; if it has points, curves, or irregular edges rather than straight sides, report its actual shape (star, cloud, arrow, burst, etc.). Do not classify non-standard shapes as "square" just because they are roughly the same size as square notes. The physical outline of the note determines the shape.
   - CRITICAL OVERLAP RULE: When a non-standard shape (star, cloud, burst, etc.) is physically overlapping or sitting on top of a square note, these are ALWAYS two completely separate sticky notes placed intentionally by the facilitator. You MUST report them as two separate JSON entries — one for the underlying square note with its own text, and one for the non-standard shape with its own distinct text. NEVER merge or combine their text into a single entry. The non-standard shape will typically be smaller, a different color, and contain its own brief annotation text (e.g. "needs rework") that is entirely different from the square note's text beneath it.

5. **Visual flow indicators**:
   - Are there hand-drawn ARROWS pointing FROM this note?
   - If yes, list the approximate target coordinates [x, y] where arrows point
   - IMPORTANT: For decision diamonds (YES/NO branches), look for REJOIN ARROWS
   - Rejoin arrows show where a branch path returns to the main workflow
   - These are often drawn on sticky notes or as curved arrows pointing back

6. **Decision branch arrows** (only for diamond shapes):
   - Look carefully for arrows showing where YES and NO branches go
   - Look for any arrows that show where branches REJOIN the main workflow
   - Common pattern: YES branch arrow points right, then a rejoin arrow points back down
   - Common pattern: NO branch arrow points down (main path continues)

Return ONLY valid JSON with this EXACT structure:
{
    "image_width": 1920,
    "image_height": 1080,
    "sticky_notes": [
        {
            "bbox": [100, 50, 250, 150],
            "text": "Zyphon Routing Loop",
            "color": "yellow",
            "shape": "square",
            "is_workflow_title": true,
            "arrows_to": []
        },
        {
            "bbox": [300, 50, 450, 150],
            "text": "Grimbolt intake",
            "color": "pink",
            "shape": "square",
            "arrows_to": [[500, 100]]
        },
        {
            "bbox": [100, 200, 250, 300],
            "text": "Flurex check",
            "color": "pink",
            "shape": "square",
            "arrows_to": [[300, 350]]
        },
        {
            "bbox": [300, 200, 450, 300],
            "text": "Vondra staging",
            "color": "pink",
            "shape": "square",
            "arrows_to": [[300, 350]]
        },
        {
            "bbox": [400, 500, 500, 600],
            "text": "Passed Zyphon threshold?",
            "color": "pink",
            "shape": "diamond",
            "arrows_to": [[600, 550], [450, 700]],
            "rejoin_arrows": [
                {"from": [650, 600], "to": [450, 750]}
            ]
        },
        {
            "bbox": [200, 700, 350, 800],
            "text": "Dispatch to Flurex bin",
            "color": "pink",
            "shape": "square",
            "arrows_to": [[200, 850]]
        },
        {
            "bbox": [310, 720, 400, 800],
            "text": "Reroute via Grimbolt",
            "color": "orange",
            "shape": "star",
            "arrows_to": []
        }
    ]
}

OVERLAP EXAMPLE EXPLAINED: The last two entries above show the correct way to report a pain point star overlapping a square note. They are two separate entries with different bboxes, different colors, different shapes, and completely different text. The square note gets its own text; the star gets its own text. They are NEVER merged.

CRITICAL RULES:
- bbox coordinates must be PRECISE - measure carefully from image edges
- For diamond shapes, the bbox should encompass the full rotated diamond
- arrows_to coordinates should point to the CENTER of the target note
- If no arrows visible, use empty array: "arrows_to": []
- rejoin_arrows are OPTIONAL - only include if you see arrows showing branch rejoin
- rejoin_arrows structure: [{"from": [x, y], "to": [x, y]}] where "from" is source note center, "to" is rejoin target center
- Be extremely accurate with coordinates - we will use them for spatial calculations
        """

        # Layout-specific prompt additions
        if flow_direction == 'horizontal-swim-lanes':
            prompt += """

LAYOUT CONTEXT — HORIZONTAL SWIM LANES:
This image uses horizontal swim lanes. Each ROW is a separate workflow, read LEFT-TO-RIGHT.
- There are multiple horizontal rows of sticky notes stacked vertically on the wall.
- Each row represents a different workflow or process area.
- Process steps within each row flow left-to-right sequentially.

WORKFLOW TITLE STICKIES — read this carefully:
- Each row typically begins with a WORKFLOW TITLE sticky note that names the entire row.
- A workflow title sticky is visually distinct from a process step in one or more of these ways:
    (a) It is positioned to the LEFT of the row with noticeably MORE space between it and the
        first process step than exists between subsequent process steps in the row.
    (b) Its text reads as a noun phrase naming a process (e.g. "Widget Assembly Flow",
        "Fulfillment Process") rather than an action step ("check inventory", "submit request").
    (c) It may be a different color from the majority of other stickies in its row.
    (d) It may be slightly above the horizontal centerline of its row rather than inline.
- When you identify a workflow title sticky, set "is_workflow_title": true in its JSON entry.
- Do NOT set is_workflow_title on speech-bubble, callout, or other non-standard shapes — those
  are always pain points.
- If you are uncertain whether a note is a title or step 1, use the spacing test: measure the
  gap between the candidate and its right neighbor vs. the typical gap between other steps in
  the row. A gap ≥ 1.5× the typical inter-step gap strongly indicates a title.

PAIN POINTS — callout and speech-bubble shapes:
- Non-standard shapes (callout bubbles, speech bubbles, stars, clouds, bursts, etc.) positioned
  near or below a row's process steps are PAIN POINTS annotating the nearest step.
- Speech bubbles and callout shapes are among the most commonly used pain point markers. They
  typically have a pointed tail and a rounded or irregular body. Do NOT classify them as
  "square" or "oval" — report their shape as "speech-bubble", "callout", or "cloud" as
  appropriate.
- Report their actual shape; never report a speech bubble as "square" or "circle".

- When multiple sticky notes are placed adjacent to each other within the same step (e.g. a
  list of items on several stickies), combine all their text into one JSON entry using the
  bounding box that encompasses all of them.
- Transcribe text EXACTLY as written — preserve acronyms, abbreviations, and unusual spellings.
  Do not correct perceived misspellings.
"""

        # Layouts with many notes per image need more token headroom.
        # Horizontal swim lanes and newspaper can have 40-60+ notes on a
        # single wide-angle wall photo; each note produces ~60-80 JSON tokens.
        # Single-column and vertical layouts are typically smaller.
        _LARGE_LAYOUT_TOKENS  = 12000  # horizontal-swim-lanes, newspaper
        _STANDARD_LAYOUT_TOKENS = 8192  # single-column, vertical-swim-lanes
        max_tok = (_LARGE_LAYOUT_TOKENS
                   if flow_direction in ('horizontal-swim-lanes', 'newspaper')
                   else _STANDARD_LAYOUT_TOKENS)

        try:
            # Send to Claude
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tok,
                temperature=0,   # deterministic — suppress text hallucination
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            # Extract the response
            response_text = message.content[0].text
            if message.stop_reason == 'max_tokens':
                # Truncated response means the JSON array is incomplete.
                # Attempt partial parse but surface a clear warning so the
                # facilitator knows to re-shoot with a closer crop or fewer
                # workflows per photo.
                print(
                    f"WARNING: analyze_workflow response truncated at "
                    f"max_tokens={max_tok} — some notes are missing from the "
                    f"JSON. Consider splitting the photo into separate uploads "
                    f"(one workflow per image) or using a closer crop."
                )
            print("Analysis complete!")
            
            # Try to parse JSON from the response
            try:
                # Find JSON in the response (Claude sometimes adds explanatory text)
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    analysis_data = json.loads(json_match.group())
                    
                    # Convert coordinate-based data to our standard format
                    if 'sticky_notes' in analysis_data:
                        notes = analysis_data['sticky_notes']
                        img_width = analysis_data.get('image_width', 2000)
                        img_height = analysis_data.get('image_height', 1500)
                        
                        # Assign temporary IDs
                        for i, note in enumerate(notes):
                            note['id'] = i + 1
                            note['parallel_with'] = None

                        # --- Pass 2: crop-and-OCR for text refinement ---
                        self._refine_text_with_crops(
                            image_path, notes, img_width, img_height)

                        strategy = get_layout_strategy(flow_direction)
                        self._annotate_note_geometry(notes)

                        # Flag notes whose short text shares no vocabulary with
                        # the rest of the pool — likely Vision hallucinations.
                        # Runs after geometry annotation (pain_point shape check
                        # inside _flag_low_confidence_text needs is_pain_point,
                        # which the layout strategy sets during sort — so we
                        # do a lightweight pre-flag here using shape directly).
                        for _n in notes:
                            shape = (_n.get('shape') or '').lower()
                            if shape and shape not in {'square', 'rectangular',
                                                       'rectangle', 'diamond'}:
                                _n['is_pain_point'] = True
                        self._flag_low_confidence_text(notes)

                        # T3.0: Rectangle Role Classifier — runs before grouping
                        process_title, lane_labels, cleaned_notes = \
                            self.classify_rectangle_roles(
                                notes, flow_direction, img_width, img_height)

                        # Group using the cleaned note pool (Tier 1 + 2 removed)
                        raw_lanes = strategy.group_workflows(
                            cleaned_notes, img_width, img_height)

                        # Post-grouping Tier 2 scan — supplements the provisional
                        # detection inside classify_rectangle_roles().
                        #
                        # The provisional pass can miss a lane header when the
                        # header sticky's center_x sits between column centres,
                        # collapsing all notes into one provisional group and
                        # preventing the second (and beyond) lane from being
                        # evaluated.  Running the same color+shape check on the
                        # ACTUAL lane assignments is always correct.
                        if flow_direction in ('vertical-swim-lanes',
                                              'horizontal-swim-lanes'):
                            refined_lanes = []
                            for lane_idx, lane in enumerate(raw_lanes):
                                if len(lane) < 2 or lane_labels.get(lane_idx):
                                    # Already labelled by provisional pass, or too
                                    # small to evaluate — leave as-is.
                                    refined_lanes.append(lane)
                                    continue

                                # Topmost note in flow direction
                                if flow_direction == 'vertical-swim-lanes':
                                    candidate = min(lane,
                                                    key=lambda n: n.get('center_y', 0))
                                else:
                                    candidate = min(lane,
                                                    key=lambda n: n.get('center_x', 0))

                                if not is_rectangle_shape(candidate.get('shape', '')):
                                    refined_lanes.append(lane)
                                    continue

                                # Pain points that Vision mis-classified as 'square'
                                # can become the leftmost note in a lane.  Guard
                                # against them here — a pre-flagged pain point is
                                # never a lane header.
                                if candidate.get('is_pain_point'):
                                    refined_lanes.append(lane)
                                    continue

                                others = [n for n in lane
                                          if n['id'] != candidate['id']]
                                if not others:
                                    refined_lanes.append(lane)
                                    continue

                                # Only count standard shapes for modal color
                                # (pain points have arbitrary colors)
                                _STANDARD = {'square', 'rectangular', 'diamond'}
                                color_counts = {}
                                for n in others:
                                    shape = (n.get('shape') or '').lower()
                                    if shape and shape not in _STANDARD:
                                        continue
                                    c = (n.get('color') or '').lower()
                                    color_counts[c] = color_counts.get(c, 0) + 1
                                if not color_counts:
                                    refined_lanes.append(lane)
                                    continue
                                modal_color = max(color_counts,
                                                  key=color_counts.get)
                                cand_color = (candidate.get('color') or '').lower()

                                if cand_color != modal_color:
                                    label = candidate.get('text', '') or ''
                                    lane_labels[lane_idx] = label
                                    refined_lanes.append(others)
                                    print(f"  [T3.0] Post-group Tier 2 header "
                                          f"(lane {lane_idx}): '{label[:40]}'")
                                else:
                                    refined_lanes.append(lane)

                            raw_lanes = refined_lanes

                        # --- Isolated-header merging pass ---
                        # When a lane header sticky is physically offset from
                        # its column (e.g. placed to the right of its process
                        # steps), group_workflows can land it alone in a 1-note
                        # lane.  The first-pass scan skips such lanes (len < 2).
                        # This second pass detects them by color contrast against
                        # the process-step modal color and assigns their text as
                        # the label for the nearest unlabelled multi-note lane.
                        if flow_direction in ('vertical-swim-lanes',
                                              'horizontal-swim-lanes'):
                            axis_key = ('center_x'
                                        if flow_direction == 'vertical-swim-lanes'
                                        else 'center_y')
                            size_dim  = (img_width
                                         if flow_direction == 'vertical-swim-lanes'
                                         else img_height)

                            # "Header-only" lane: exactly one is_workflow_title
                            # note plus any number of pain points, but no actual
                            # process steps.  Occurs when a swim-lane header sits
                            # in the gap between two Y-bands and a stray pain point
                            # lands in the same inter-lane gap, giving len(lane)==2
                            # and bypassing the original len==1 isolated check.
                            def _header_only_lane(lane):
                                proc = [n for n in lane
                                        if not n.get('is_pain_point')
                                        and not n.get('is_workflow_title')]
                                title = [n for n in lane
                                         if n.get('is_workflow_title')]
                                return len(proc) == 0 and len(title) == 1

                            multi_note = [(i, lane)
                                          for i, lane in enumerate(raw_lanes)
                                          if len(lane) >= 2
                                          and not _header_only_lane(lane)]
                            isolated   = [(i, lane)
                                          for i, lane in enumerate(raw_lanes)
                                          if len(lane) == 1
                                          or _header_only_lane(lane)]

                            if isolated and multi_note:
                                # Track IDs absorbed in this post-group pass
                                tier2_ids: set = set()
                                # Modal process-step color across all multi-note lanes
                                # (exclude non-standard shapes — pain points)
                                _STANDARD = {'square', 'rectangular', 'diamond'}
                                all_colors: dict = {}
                                for _, lane in multi_note:
                                    for n in lane:
                                        shape = (n.get('shape') or '').lower()
                                        if shape and shape not in _STANDARD:
                                            continue
                                        c = (n.get('color') or '').lower()
                                        all_colors[c] = all_colors.get(c, 0) + 1
                                global_modal = (max(all_colors, key=all_colors.get)
                                                if all_colors else '')

                                absorbed: set = set()
                                for iso_idx, iso_lane in isolated:
                                    # For header-only multi-note lanes prefer the
                                    # explicitly-flagged title note; for true
                                    # single-note lanes use the only note.
                                    title_cands = [n for n in iso_lane
                                                   if n.get('is_workflow_title')]
                                    cand = (title_cands[0] if title_cands
                                            else iso_lane[0])
                                    cand_color = (cand.get('color') or '').lower()

                                    # Skip if same color as process steps AND Vision
                                    # did not explicitly flag it as a workflow title.
                                    # On dark/colored walls Vision can misread the
                                    # header color — the explicit flag overrides the
                                    # color gate so those headers are not dropped.
                                    if (cand_color == global_modal
                                            and not cand.get('is_workflow_title')):
                                        continue  # same color as steps → not a header

                                    # Nearest unlabelled multi-note lane by centroid
                                    cand_pos = cand.get(axis_key, 0)
                                    best_idx, best_dist = None, float('inf')
                                    for multi_idx, lane in multi_note:
                                        if lane_labels.get(multi_idx):
                                            continue  # already has a label
                                        lane_pos = (sum(n.get(axis_key, 0)
                                                        for n in lane) / len(lane))
                                        d = abs(cand_pos - lane_pos)
                                        if d < best_dist:
                                            best_dist, best_idx = d, multi_idx

                                    if (best_idx is not None
                                            and best_dist < (size_dim or 1000) * 0.5):
                                        label = cand.get('text', '') or ''
                                        lane_labels[best_idx] = label
                                        tier2_ids.add(cand['id'])
                                        absorbed.add(iso_idx)
                                        print(f"  [T3.0] Isolated Tier 2 header "
                                              f"(lane {iso_idx}) -> lane {best_idx}: "
                                              f"'{label[:40]}'")

                                if absorbed:
                                    kept = [(old_i, lane)
                                            for old_i, lane in enumerate(raw_lanes)
                                            if old_i not in absorbed]
                                    raw_lanes = [lane for _, lane in kept]
                                    old_to_new_lane = {old_i: new_i
                                                       for new_i, (old_i, _)
                                                       in enumerate(kept)}
                                    lane_labels = {
                                        old_to_new_lane[k]: v
                                        for k, v in lane_labels.items()
                                        if k in old_to_new_lane
                                    }

                        # Wrap each lane list with its lane_label metadata.
                        workflows = [
                            {'notes': lane, 'lane_label': lane_labels.get(i)}
                            for i, lane in enumerate(raw_lanes)
                        ]

                        print(f"\nDetected {len(workflows)} workflow(s) using '{strategy.name}' layout")

                        # Process each workflow independently
                        all_processed_notes = []
                        workflow_metadata = []

                        for wf_idx, workflow in enumerate(workflows):
                            workflow_notes = workflow['notes']
                            lane_label     = workflow.get('lane_label')
                            label_tag = f" [{lane_label}]" if lane_label else ""
                            print(f"\n--- Processing Workflow {wf_idx + 1} ({len(workflow_notes)} notes){label_tag} ---")

                            # Detect relationships within this workflow
                            self._calculate_relationships_from_coordinates(workflow_notes, img_width, img_height, flow_direction)

                            # Sort spatially within this workflow
                            strategy.sort_workflow(workflow_notes, img_width, img_height)

                            all_processed_notes.extend(workflow_notes)

                            # Store workflow metadata (with lane_label for PDF)
                            workflow_metadata.append({
                                'workflow_id': wf_idx + 1,
                                'note_count': len(workflow_notes),
                                'note_ids': [n['id'] for n in workflow_notes],
                                'lane_label': lane_label,
                            })
                        
                        # Re-assign IDs globally after sorting
                        # Create mapping of old IDs to new IDs
                        old_to_new_id = {}
                        for i, note in enumerate(all_processed_notes):
                            old_id = note['id']
                            new_id = i + 1
                            old_to_new_id[old_id] = new_id
                            note['id'] = new_id
                        
                        # Update workflow_metadata note_ids to use new IDs.
                        # workflow_metadata is built before renumbering, so its
                        # note_ids still reference old IDs.  Without this update
                        # the PDF renderer's notes_dict lookup (keyed by new IDs)
                        # misses every note and renders nothing for swim lanes.
                        for wf in workflow_metadata:
                            wf['note_ids'] = [
                                old_to_new_id[nid]
                                for nid in wf['note_ids']
                                if nid in old_to_new_id
                            ]

                        # Update all references to use new IDs
                        for note in all_processed_notes:
                            # Update parallel_with references
                            if note.get('parallel_with') in old_to_new_id:
                                note['parallel_with'] = old_to_new_id[note['parallel_with']]
                            
                            # Update decision_branches references
                            if note.get('decision_branches'):
                                branches = note['decision_branches']
                                if branches.get('yes_next_step') in old_to_new_id:
                                    branches['yes_next_step'] = old_to_new_id[branches['yes_next_step']]
                                if branches.get('no_next_step') in old_to_new_id:
                                    branches['no_next_step'] = old_to_new_id[branches['no_next_step']]
                                if branches.get('rejoin_step') in old_to_new_id:
                                    branches['rejoin_step'] = old_to_new_id[branches['rejoin_step']]
                            if note.get('is_pain_point') and note.get('pain_point_for') in old_to_new_id:
                                note['pain_point_for'] = old_to_new_id[note['pain_point_for']]
                        
                        analysis_data['sticky_notes'] = all_processed_notes
                        analysis_data['workflow_sequence'] = [note['id'] for note in all_processed_notes if not note.get('is_pain_point')]
                        analysis_data['workflows'] = workflow_metadata
                        analysis_data['flow_direction'] = flow_direction
                        analysis_data['process_title'] = process_title
                        
                        print(f"\nFinal sequence: {analysis_data['workflow_sequence']}")
                        
                    return analysis_data
                else:
                    return {"raw_analysis": response_text}
                
            except Exception as e:
                print(f"JSON parsing failed: {e}")
                return {"raw_analysis": response_text}
                
        except Exception as e:
            print(f"Analysis failed: {e}")
            return None

    def find_duplicate_notes(self, all_results):
        """Find potentially duplicate sticky notes across multiple images"""
        duplicates = []
        
        # Extract all notes from all analyses
        all_notes = []
        for i, result in enumerate(all_results):
            if result['status'] == 'success' and 'sticky_notes' in result['analysis']:
                for note in result['analysis']['sticky_notes']:
                    note['source_image'] = i
                    note['source_filename'] = result['filename']
                    all_notes.append(note)
        
        # Find potential duplicates based on text similarity
        for i, note1 in enumerate(all_notes):
            for j, note2 in enumerate(all_notes[i+1:], i+1):
                if self.notes_similar(note1, note2):
                    duplicates.append({
                        'note1': note1,
                        'note2': note2,
                        'similarity_score': self.calculate_similarity(note1, note2),
                        'suggested_action': 'merge'
                    })
        
        return duplicates
    
    def notes_similar(self, note1, note2):
        """Check if two notes are potentially the same physical sticky note.

        Requires BOTH high text similarity AND spatial proximity so that
        two legitimate notes with identical text (e.g. two 'manual' pain
        points attached to different steps) are never merged.

        Spatial proximity is evaluated using center coordinates when
        available, falling back to grid_position for overview-path notes
        that lack bbox data.  Two notes are only considered duplicates
        when their distance is less than half the median note size
        (~40 px for typical compressed images, ~80 px for full-res).
        """
        text1 = note1.get('text', '').lower().strip()
        text2 = note2.get('text', '').lower().strip()

        if not text1 or not text2:
            return False

        # Text similarity gate
        text_sim = SequenceMatcher(None, text1, text2).ratio()
        if text_sim <= 0.8:
            return False

        # Spatial proximity gate — must ALSO pass to be considered a duplicate.
        # Use center_x/center_y when present (single-photo path).
        cx1 = note1.get('center_x')
        cy1 = note1.get('center_y')
        cx2 = note2.get('center_x')
        cy2 = note2.get('center_y')

        if cx1 is not None and cx2 is not None:
            dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
            # Notes further than ~60 px apart are distinct physical stickies.
            # Threshold is intentionally tight — Vision bbox jitter is ≤ 15 px,
            # so a true double-detection will always be well under 60 px.
            if dist > 60:
                return False
        else:
            # Multi-photo path: compare grid positions as a coarse proxy.
            # Only flag as duplicate when both grid row AND column match exactly.
            gp1 = note1.get('grid_position', {})
            gp2 = note2.get('grid_position', {})
            if gp1 and gp2:
                row_match = gp1.get('grid_row') == gp2.get('grid_row')
                col_match = gp1.get('grid_col') == gp2.get('grid_col')
                if not (row_match and col_match):
                    return False
            # If neither coordinate system is available, fall back to
            # text-only check — this preserves previous behaviour for
            # edge-case note objects that carry neither field.

        return True
    
    def calculate_similarity(self, note1, note2):
        """Calculate similarity score between two notes"""
        text_similarity = SequenceMatcher(None, 
                                        note1.get('text', '').lower(), 
                                        note2.get('text', '').lower()).ratio()
        
        # Factor in color similarity
        color_match = 1.0 if note1.get('color') == note2.get('color') else 0.5
        
        # Weighted average
        return (text_similarity * 0.8) + (color_match * 0.2)
    
    def classify_rectangle_roles(self, notes, flow_direction, img_width, img_height):
        """Pre-processing pass that classifies rectangle notes into roles before
        layout grouping runs.

        Tier 1 — Banner: Large rectangle spanning the top of the wall.
            Becomes process_title in the returned result.
        Tier 2 — Lane Header: First note in each group's flow direction that is
            rectangle-shaped AND a different color from the modal color of its
            group.  Becomes lane_label for that workflow group.
        Tier 3 — Process Step: Everything else (unchanged).

        Coordinate system: image coordinates — Y=0 at top, Y increases downward.
        "Top of wall" therefore corresponds to LOW center_y values.

        Args:
            notes: full note pool after _annotate_note_geometry() has been called
            flow_direction: layout type string
            img_width, img_height: image pixel dimensions

        Returns:
            process_title (str | None)
            lane_labels   (dict: group_index -> label_string)
            cleaned_notes (list: Tier 1 + Tier 2 notes removed)
        """
        if not notes:
            return None, {}, []

        print("  [T3.0] Running Rectangle Role Classifier...")

        # ------------------------------------------------------------------ #
        # Tier 1 — Banner detection
        # For horizontal swim lanes the "top 20%" of the image IS the first
        # lane — full of regular process steps.  A step with a slightly
        # larger bbox falsely triggers the 1.5× size threshold and gets
        # promoted to the workflow title.  Skip Tier 1 for horizontal swim
        # lanes; they rely entirely on Tier 2 lane headers.
        # Vertical swim lanes keep Tier 1 active because the column-header
        # row is physically at the top of the image, so the heuristic works.
        # ------------------------------------------------------------------ #

        widths  = [n.get('width',  0) for n in notes]
        heights = [n.get('height', 0) for n in notes]
        median_w = median(widths)  if widths  else 1
        median_h = median(heights) if heights else 1

        # Image coords: Y=0 at top, increases downward.
        # "Top 20%" = notes with center_y <= 0.2 * max_y
        max_y = max((n.get('center_y', 0) for n in notes), default=1) or 1
        top_threshold = 0.2 * max_y

        banner_candidates = []
        if flow_direction == 'horizontal-swim-lanes':
            print(f"  [T3.0] Tier 1 banner skipped "
                  f"(horizontal swim lanes use Tier 2 lane headers only)")
        else:
            for note in notes:
                if not is_rectangle_shape(note.get('shape', '')):
                    continue
                size_qualifies = (
                    note.get('width',  0) >= 1.5 * median_w or
                    note.get('height', 0) >= 1.5 * median_h
                )
                y_in_top = note.get('center_y', 0) <= top_threshold
                if size_qualifies and y_in_top:
                    banner_candidates.append(note)

        process_title = None
        tier1_ids = set()
        if banner_candidates:
            # Take the largest candidate by area
            banner_note = max(
                banner_candidates,
                key=lambda n: n.get('width', 0) * n.get('height', 0)
            )
            process_title = banner_note.get('text', '') or None
            tier1_ids.add(banner_note['id'])
            print(f"  [T3.0] Tier 1 banner: '{(process_title or '')[:50]}'")

            # "sticky-on-background" pattern: when the detected banner is a
            # plain rectangular background card, the real title is a smaller
            # sticky note placed on top of it.  If such an overlay sticky
            # exists, prefer its text and also remove it from the sequence.
            if banner_note.get('shape', '').lower() in ('rectangular', 'rectangle'):
                banner_cx = banner_note.get('center_x', 0)
                banner_cy = banner_note.get('center_y', 0)
                banner_w  = max(banner_note.get('width',  1), 1)
                banner_h  = max(banner_note.get('height', 1), 1)
                for n in notes:
                    if n['id'] in tier1_ids:
                        continue
                    # Skip other rectangles and diamonds — only plain stickies
                    if n.get('shape', '').lower() in ('rectangular', 'rectangle', 'diamond'):
                        continue
                    if not (n.get('text') or '').strip():
                        continue
                    # The sticky's center must lie within the banner footprint
                    if (abs(n.get('center_x', 0) - banner_cx) < banner_w * 0.6 and
                            abs(n.get('center_y', 0) - banner_cy) < banner_h * 0.6):
                        process_title = n.get('text') or process_title
                        tier1_ids.add(n['id'])
                        print(f"  [T3.0] Tier 1 overlay sticky: '{(process_title or '')[:50]}'")
                        break

        remaining = [n for n in notes if n['id'] not in tier1_ids]

        # Secondary title detection for single-column / newspaper layouts.
        # Handles the common wall pattern: one sticky at the top of the board,
        # vertically isolated from the main column, used as the workflow title.
        # Only runs when Tier 1 size-based detection found nothing.
        if process_title is None and flow_direction in ('single-column', 'newspaper'):
            top_candidates = sorted(
                [n for n in remaining
                 if n.get('center_y', 0) <= top_threshold
                 and (n.get('text') or '').strip()],
                key=lambda n: n.get('center_y', 0)
            )
            for candidate in top_candidates:
                cand_y = candidate.get('center_y', 0)
                # Must be isolated: no other remaining note within ±50 px vertically
                same_level = [
                    n for n in remaining
                    if n['id'] != candidate['id']
                    and abs(n.get('center_y', 0) - cand_y) < 50
                ]
                if not same_level:
                    process_title = candidate.get('text') or None
                    if process_title:
                        tier1_ids.add(candidate['id'])
                        remaining = [n for n in remaining if n['id'] != candidate['id']]
                        print(f"  [T3.0] Tier 1 isolated-top title: '{process_title[:50]}'")
                    break

        # ------------------------------------------------------------------ #
        # Tier 2 — Lane Header detection (swim-lane layouts only)
        # Uses the same gap constants as the layout strategies so that the
        # provisional grouping here matches the final grouping exactly.
        # Both thresholds are relative to image dimensions so they work on
        # small/compressed images (e.g. 486 px wide phone shots) as well as
        # large ones.  The formula mirrors VerticalSwimLaneStrategy.group_workflows.
        # IMPORTANT: LANE_GAP_HORIZONTAL must use the SAME formula as
        # HorizontalSwimLaneStrategy.group_workflows (0.08 multiplier, min 90)
        # so that the provisional T3.0 groups match the actual lane groups.
        # ------------------------------------------------------------------ #
        LANE_GAP_VERTICAL   = max(50, min(150, (img_width  or 750) * 0.12))
        LANE_GAP_HORIZONTAL = max(40, min(90,  (img_height or 750) * 0.08))

        lane_labels = {}
        tier2_ids   = set()

        if flow_direction == 'vertical-swim-lanes':
            # Provisional column grouping: sort by center_x, split on X gap
            sorted_x = sorted(remaining, key=lambda n: n.get('center_x', 0))
            groups = []
            if sorted_x:
                groups = [[sorted_x[0]]]
                for note in sorted_x[1:]:
                    gap = note.get('center_x', 0) - groups[-1][-1].get('center_x', 0)
                    if gap > LANE_GAP_VERTICAL:
                        groups.append([note])
                    else:
                        groups[-1].append(note)

            for grp_idx, group in enumerate(groups):
                if len(group) < 2:
                    continue  # single note → Tier 3, no comparison possible

                # First note in flow direction = topmost (lowest center_y)
                candidate = min(group, key=lambda n: n.get('center_y', 0))

                if not is_rectangle_shape(candidate.get('shape', '')):
                    continue  # not rectangle-shaped → Tier 3

                other_notes = [n for n in group if n['id'] != candidate['id']]
                if not other_notes:
                    continue

                # Modal color of standard-shape group members only
                # (pain points have arbitrary colors and must not skew the count)
                _STANDARD = {'square', 'rectangular', 'diamond'}
                color_counts = {}
                for n in other_notes:
                    shape = (n.get('shape') or '').lower()
                    if shape and shape not in _STANDARD:
                        continue
                    c = (n.get('color') or '').lower()
                    color_counts[c] = color_counts.get(c, 0) + 1
                if not color_counts:
                    continue
                modal_color = max(color_counts, key=color_counts.get)

                candidate_color = (candidate.get('color') or '').lower()
                if candidate_color != modal_color:
                    label = candidate.get('text', '') or ''
                    lane_labels[grp_idx] = label
                    tier2_ids.add(candidate['id'])
                    print(f"  [T3.0] Tier 2 lane header (col {grp_idx}): '{label[:40]}'")

        elif flow_direction == 'horizontal-swim-lanes':
            # Provisional row grouping: sort by center_y, split on Y gap.
            # Exclude pre-flagged pain points (non-standard shapes) because
            # they sit BELOW their anchor step and can fill inter-lane gaps,
            # preventing clean lane splits — same guard the actual strategy uses.
            standard_remaining = [n for n in remaining
                                   if not n.get('is_pain_point')]
            sorted_y = sorted(standard_remaining, key=lambda n: n.get('center_y', 0))
            groups = []
            if sorted_y:
                groups = [[sorted_y[0]]]
                for note in sorted_y[1:]:
                    gap = note.get('center_y', 0) - groups[-1][-1].get('center_y', 0)
                    if gap > LANE_GAP_HORIZONTAL:
                        groups.append([note])
                    else:
                        groups[-1].append(note)

            for grp_idx, group in enumerate(groups):
                if len(group) < 2:
                    continue

                # Prefer any note Vision explicitly flagged as the workflow
                # title; fall back to the leftmost (min center_x).  This
                # handles cut-off headers whose center_x is not the smallest
                # in the row (e.g. "Data Flow" at image edge in TC4).
                title_flagged = [
                    n for n in group
                    if n.get('is_workflow_title')
                    and is_rectangle_shape(n.get('shape', ''))
                    and not n.get('is_pain_point')
                ]
                candidate = (
                    min(title_flagged, key=lambda n: n.get('center_x', 0))
                    if title_flagged
                    else min(group, key=lambda n: n.get('center_x', 0))
                )

                if not is_rectangle_shape(candidate.get('shape', '')):
                    print(f"  [T3.0] Row {grp_idx}: leftmost note "
                          f"shape='{candidate.get('shape','')}' not rectangle — skip")
                    continue

                # Pain point mis-classified as square by Vision is never a header
                if candidate.get('is_pain_point'):
                    print(f"  [T3.0] Row {grp_idx}: leftmost note flagged as "
                          f"pain point — skip")
                    continue

                other_notes = [n for n in group if n['id'] != candidate['id']]
                if not other_notes:
                    continue

                # Diagnostic: log what we're evaluating so failures are traceable
                print(f"  [T3.0] Row {grp_idx}: evaluating candidate "
                      f"text='{(candidate.get('text') or '')[:30]}' "
                      f"shape='{candidate.get('shape','')}' "
                      f"color='{candidate.get('color','')}' "
                      f"is_workflow_title={candidate.get('is_workflow_title',False)}")

                # --- Signal 1: Vision explicitly flagged this note as a title ---
                if candidate.get('is_workflow_title'):
                    label = candidate.get('text', '') or ''
                    lane_labels[grp_idx] = label
                    tier2_ids.add(candidate['id'])
                    print(f"  [T3.0] Tier 2 lane header via is_workflow_title "
                          f"(row {grp_idx}): '{label[:40]}'")
                    continue

                # --- Signal 2: Color contrast (original logic) ---
                # Only count standard shapes for modal color
                _STANDARD = {'square', 'rectangular', 'diamond'}
                color_counts = {}
                for n in other_notes:
                    shape = (n.get('shape') or '').lower()
                    if shape and shape not in _STANDARD:
                        continue
                    c = (n.get('color') or '').lower()
                    color_counts[c] = color_counts.get(c, 0) + 1

                modal_color = (max(color_counts, key=color_counts.get)
                               if color_counts else '')
                candidate_color = (candidate.get('color') or '').lower()

                if modal_color and candidate_color != modal_color:
                    label = candidate.get('text', '') or ''
                    lane_labels[grp_idx] = label
                    tier2_ids.add(candidate['id'])
                    print(f"  [T3.0] Tier 2 lane header via color contrast "
                          f"(row {grp_idx}): '{label[:40]}'")
                    continue

                print(f"  [T3.0] Row {grp_idx}: color contrast miss — "
                      f"candidate='{candidate_color}' modal='{modal_color}'")

                # --- Signal 3: Spatial isolation fallback ---
                # When Vision reports the header as the same color as process
                # steps (common on dark/colored walls), check whether the gap
                # between the candidate and its right neighbor is disproportionately
                # large compared to the typical inter-step gap in the row.
                # A gap ≥ 1.8× the median inter-step gap indicates the leftmost
                # note is a standalone title, not step 1 of the flow.
                sorted_by_x = sorted(group, key=lambda n: n.get('center_x', 0))
                if len(sorted_by_x) >= 3:
                    inter_step_gaps = [
                        sorted_by_x[i + 1].get('center_x', 0) -
                        sorted_by_x[i].get('center_x', 0)
                        for i in range(1, len(sorted_by_x) - 1)
                    ]
                    if inter_step_gaps:
                        median_gap = sorted(inter_step_gaps)[len(inter_step_gaps) // 2]
                        first_gap = (sorted_by_x[1].get('center_x', 0) -
                                     sorted_by_x[0].get('center_x', 0))
                        ratio = (first_gap / median_gap) if median_gap > 0 else 0
                        print(f"  [T3.0] Row {grp_idx}: spatial gap "
                              f"first={first_gap:.0f}px median={median_gap:.0f}px "
                              f"ratio={ratio:.2f}x (need >=1.80x)")
                        if median_gap > 0 and first_gap >= 1.8 * median_gap:
                            label = candidate.get('text', '') or ''
                            lane_labels[grp_idx] = label
                            tier2_ids.add(candidate['id'])
                            print(f"  [T3.0] Tier 2 lane header via spatial isolation "
                                  f"(row {grp_idx}, gap ratio "
                                  f"{ratio:.1f}x): '{label[:40]}'")

        # For single-column and newspaper layouts Tier 2 is not applicable.

        removed_total = len(tier1_ids) + len(tier2_ids)
        cleaned_notes = [n for n in remaining if n['id'] not in tier2_ids]
        print(
            f"  [T3.0] Removed {removed_total} header note(s) "
            f"({len(tier1_ids)} banner, {len(tier2_ids)} lane header). "
            f"{len(cleaned_notes)} process-step notes remain."
        )
        return process_title, lane_labels, cleaned_notes

    def _annotate_note_geometry(self, notes):
        """Pre-compute center and size values used by layout strategies."""
        for note in notes:
            bbox = note.get('bbox', [0, 0, 100, 100])
            note['center_x'] = (bbox[0] + bbox[2]) / 2
            note['center_y'] = (bbox[1] + bbox[3]) / 2
            note['width'] = bbox[2] - bbox[0]
            note['height'] = bbox[3] - bbox[1]

    def _flag_low_confidence_text(self, notes):
        """Mark notes whose text is likely a Vision hallucination.

        Hallucinations typically produce short (1-3 word) text that shares
        no vocabulary with the rest of the note pool.  Legitimate short
        notes (e.g. 'Manual', 'QSA', 'Azure') will appear as acronyms or
        terms that recur elsewhere on the wall.  A truly orphaned short
        string that matches nothing else is a strong hallucination signal.

        Sets note['low_confidence'] = True on suspects so the Review UI
        can highlight them for facilitator confirmation.  Does NOT remove
        or alter the text — the note still appears in the PDF, just flagged.

        Exclusions:
        - Pain points (non-standard shapes) — short text is expected
        - Notes already marked [illegible] — already flagged by Vision
        - Notes whose text is a recognised [illegible] placeholder
        - Single-character or empty strings (filtered upstream)
        """
        # Build a vocabulary of all words across all notes (lowercase, ≥3 chars)
        vocab: set = set()
        for note in notes:
            text = (note.get('text') or '').lower()
            if '[illegible]' in text:
                continue
            for word in text.split():
                clean = word.strip('.,;:!?()-')
                if len(clean) >= 3:
                    vocab.add(clean)

        flagged = 0
        for note in notes:
            # Skip pain points — short text is intentional
            if note.get('is_pain_point'):
                continue

            text = (note.get('text') or '').strip()
            if not text or '[illegible]' in text.lower():
                continue

            words = text.split()
            # Only evaluate short notes (1-3 words)
            if len(words) > 3:
                continue

            # Check whether any word in this note's text appears elsewhere
            note_words = {w.strip('.,;:!?()-').lower() for w in words
                          if len(w.strip('.,;:!?()-')) >= 3}
            if not note_words:
                continue

            # Count how many of this note's words appear in the broader vocab
            # (subtract the words contributed by this note itself)
            note_vocab_contribution = note_words & vocab
            shared = sum(
                1 for w in note_vocab_contribution
                if sum(1 for n in notes
                       if w in (n.get('text') or '').lower()
                       and n['id'] != note['id']) > 0
            )

            if shared == 0:
                note['low_confidence'] = True
                flagged += 1
                print(f"  [LowConf] Flagged suspect text: '{text[:50]}'")

        if flagged:
            print(f"  [LowConf] {flagged} note(s) flagged as low-confidence text")

    def _calculate_relationships_from_coordinates(self, notes, img_width, img_height, flow_direction='single-column'):
        """
        Calculate parallel relationships and decision branches from bounding box coordinates.
        Much more accurate than text-based position descriptions.
        """
        # Calculate center points for all notes
        for note in notes:
            bbox = note.get('bbox', [0, 0, 100, 100])
            note['center_x'] = (bbox[0] + bbox[2]) / 2
            note['center_y'] = (bbox[1] + bbox[3]) / 2
            note['width'] = bbox[2] - bbox[0]
            note['height'] = bbox[3] - bbox[1]

        # Detect parallel relationships (notes at same Y-level, side-by-side)
        # Skip for horizontal swim lanes: all notes in a row share similar Y,
        # so Y-tolerance parallel detection would incorrectly fire on every pair.
        PARALLEL_Y_TOLERANCE = 30  # pixels

        if flow_direction == 'horizontal-swim-lanes':
            print("  Parallel detection skipped for horizontal swim lanes")

        for i, note1 in enumerate(notes):
            if flow_direction == 'horizontal-swim-lanes':
                break
            if note1.get('parallel_with'):
                continue  # Already assigned
            
            # Skip headers (rectangular shape at top)
            if note1.get('shape') == 'rectangular' and note1['center_y'] < img_height * 0.2:
                continue
            
            # Skip diamond shapes - they are decision points, not parallel candidates
            if note1.get('shape') == 'diamond':
                continue
                
            for note2 in notes[i+1:]:
                if note2.get('parallel_with'):
                    continue
                
                # Skip headers
                if note2.get('shape') == 'rectangular' and note2['center_y'] < img_height * 0.2:
                    continue
                
                # Skip diamond shapes
                if note2.get('shape') == 'diamond':
                    continue
                
                # Check if Y-coordinates are aligned (within tolerance)
                y_diff = abs(note1['center_y'] - note2['center_y'])
                x_diff = abs(note1['center_x'] - note2['center_x'])
                
                # Must be at same Y-level AND horizontally adjacent
                if y_diff <= PARALLEL_Y_TOLERANCE and 50 < x_diff < 200:
                    # They're at the same level and side-by-side - mark as parallel
                    note1['parallel_with'] = note2['id']
                    note2['parallel_with'] = note1['id']
                    print(f"  Parallel detected: {note1.get('text', '?')[:20]} <-> {note2.get('text', '?')[:20]} (Y-diff: {y_diff:.0f}px, X-diff: {x_diff:.0f}px)")
                    break  # Only one parallel partner per note
        
        # Detect decision branches (for diamond shapes)
        for note in notes:
            if note.get('shape') != 'diamond':
                continue
            
            print(f"  Decision diamond found: {note.get('text', '?')[:30]}")
            
            diamond_x = note['center_x']
            diamond_y = note['center_y']
            
            # Look for notes to the RIGHT (Yes branch) and BELOW (No branch)
            yes_candidate = None
            no_candidate = None
            yes_distance = float('inf')
            no_distance = float('inf')
            
            for other in notes:
                if other['id'] == note['id']:
                    continue

                # Skip non-standard shapes (pain points, stars, spirals, etc.)
                # They are annotation markers, never valid decision-branch targets.
                # Diamonds ARE valid — sequential decision points are common.
                valid_branch_shapes = {'square', 'rectangular', 'rectangle', 'diamond'}
                if (other.get('shape') or '').lower() not in valid_branch_shapes:
                    continue

                other_x = other['center_x']
                other_y = other['center_y']

                # Check for YES branch (to the right, roughly same Y-level)
                if other_x > diamond_x + 50:  # At least 50px to the right
                    if abs(other_y - diamond_y) < 150:  # Within 150px vertically
                        distance = abs(other_x - diamond_x) + abs(other_y - diamond_y)
                        if distance < yes_distance:
                            yes_distance = distance
                            yes_candidate = other
                
                # Check for NO branch (below, roughly same X-level or slightly offset)
                if other_y > diamond_y + 50:  # At least 50px below
                    if abs(other_x - diamond_x) < 200:  # Within 200px horizontally
                        distance = abs(other_y - diamond_y) + abs(other_x - diamond_x)
                        if distance < no_distance:
                            no_distance = distance
                            no_candidate = other
            
            # Find rejoin point using three methods (in priority order):
            # 1. Explicit rejoin arrows from Vision API
            # 2. Default assumption: YES rejoins where NO goes (main path continues)
            # 3. Spatial heuristic: find note below both branches
            rejoin_candidate = None
            rejoin_method = None
            
            # METHOD 1: Check for explicit rejoin arrows from Vision API
            rejoin_arrows = note.get('rejoin_arrows', [])
            if rejoin_arrows and yes_candidate:
                # Look for arrow from YES branch area pointing to a target
                for arrow in rejoin_arrows:
                    arrow_from = arrow.get('from', [])
                    arrow_to = arrow.get('to', [])
                    
                    if len(arrow_from) == 2 and len(arrow_to) == 2:
                        # Find which note this arrow points to
                        target_x, target_y = arrow_to
                        min_distance = float('inf')
                        arrow_target = None
                        
                        for other in notes:
                            if other['id'] == note['id']:
                                continue
                            distance = ((other['center_x'] - target_x)**2 + (other['center_y'] - target_y)**2)**0.5
                            if distance < min_distance and distance < 100:  # Within 100px tolerance
                                min_distance = distance
                                arrow_target = other
                        
                        if arrow_target:
                            rejoin_candidate = arrow_target
                            rejoin_method = 'explicit_arrow'
                            print(f"    Found explicit rejoin arrow to {arrow_target.get('text', '?')[:20]}")
                            break
            
            # METHOD 2: Default assumption - YES rejoins where NO goes (most common pattern)
            if not rejoin_candidate and yes_candidate and no_candidate:
                # The YES branch (exception) rejoins at the NO branch destination (main path)
                rejoin_candidate = no_candidate
                rejoin_method = 'default_rejoin_at_no'
                print(f"    Using default: YES rejoins at NO branch")
            
            # METHOD 3: Spatial heuristic - find note below both branches
            if not rejoin_candidate and yes_candidate and no_candidate:
                yes_y = yes_candidate['center_y']
                no_y = no_candidate['center_y']
                max_branch_y = max(yes_y, no_y)
                
                rejoin_distance = float('inf')
                for other in notes:
                    if other['id'] in [note['id'], yes_candidate['id'], no_candidate['id']]:
                        continue
                    
                    if other['center_y'] > max_branch_y + 20:
                        # This note is below both branches
                        distance = other['center_y'] - max_branch_y
                        if distance < rejoin_distance:
                            rejoin_distance = distance
                            rejoin_candidate = other
                
                if rejoin_candidate:
                    rejoin_method = 'spatial_below_both'
                    print(f"    Spatial detection: rejoin below both branches")
            
            # Assign decision branches
            if yes_candidate or no_candidate:
                # Validate candidates (prevent self-reference)
                yes_id = yes_candidate['id'] if yes_candidate and yes_candidate['id'] != note['id'] else None
                no_id = no_candidate['id'] if no_candidate and no_candidate['id'] != note['id'] else None
                rejoin_id = rejoin_candidate['id'] if rejoin_candidate and rejoin_candidate['id'] != note['id'] else None
                
                note['decision_branches'] = {
                    'yes_next_step': yes_id,
                    'no_next_step': no_id,
                    'rejoin_step': rejoin_id,
                    'rejoin_method': rejoin_method,  # Track which method was used
                    'yes_label': 'Yes',
                    'no_label': 'No'
                }
                print(f"    Yes -> {yes_candidate.get('text', 'None')[:20] if yes_candidate and yes_id else 'None'}")
                print(f"    No  -> {no_candidate.get('text', 'None')[:20] if no_candidate and no_id else 'None'}")
                print(f"    Rejoin -> {rejoin_candidate.get('text', 'None')[:20] if rejoin_candidate and rejoin_id else 'None'}")
    

# Test function
if __name__ == "__main__":
    analyzer = StickyNoteAnalyzer()
    
    # Test with a sample image (you'll replace this path)
    test_image = input("Enter path to test image: ")
    
    if os.path.exists(test_image):
        result = analyzer.analyze_workflow(test_image)
        if result:
            print("\n" + "="*50)
            print("ANALYSIS RESULT:")
            print("="*50)
            print(json.dumps(result, indent=2))
        else:
            print("Analysis failed")
    else:
        print("Image file not found")






