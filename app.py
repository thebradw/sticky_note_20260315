# app.py - Main Flask Application
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import json
from werkzeug.utils import secure_filename
from image_analyzer import StickyNoteAnalyzer
from pdf_renderer import ProcessMapFlowable
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-for-sessions'  # Change this to something random

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)

# Initialize the analyzer
analyzer = StickyNoteAnalyzer()

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

VALID_FLOW_DIRECTIONS = {
    'single-column',
    'newspaper',
    'horizontal-swim-lanes',
    'vertical-swim-lanes',
}

def normalize_flow_direction(value):
    """Map user input to a supported layout value."""
    if not value:
        return 'single-column'
    value = value.lower()
    alias_map = {
        'left-right': 'single-column',
    }
    normalized = alias_map.get(value, value)
    return normalized if normalized in VALID_FLOW_DIRECTIONS else 'single-column'

# Store session data (in production, use a database)
sessions = {}

@app.route('/')
def index():
    """Main upload page"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle multiple file uploads - overview first, then detail photos"""

    if 'files' not in request.files:
        flash('No files selected')
        return redirect(url_for('index'))

    files = request.files.getlist('files')

    if not files or all(f.filename == '' for f in files):
        flash('No files selected')
        return redirect(url_for('index'))

    # Get flow direction from form
    flow_direction = normalize_flow_direction(request.form.get('flow_direction'))

    # Create session ID for this workflow
    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        'uploaded_files': [],
        'analysis_results': [],
        'timestamp': datetime.now(),
        'status': 'uploaded',
        'flow_direction': flow_direction,
        'multi_photo': len(files) > 1
    }

    # Process uploaded files
    # First file = overview, remaining files = detail photos
    uploaded_count = 0
    for i, file in enumerate(files):
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{session_id}_{timestamp}_{i}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            photo_type = 'overview' if i == 0 else 'detail'

            sessions[session_id]['uploaded_files'].append({
                'filename': filename,
                'original_name': file.filename,
                'filepath': filepath,
                'photo_type': photo_type,
                'index': i
            })
            uploaded_count += 1

    if uploaded_count == 0:
        flash('No valid image files were uploaded')
        return redirect(url_for('index'))

    flash(f'Successfully uploaded {uploaded_count} images (1 overview + {uploaded_count - 1} detail photos)')
    return redirect(url_for('analyze', session_id=session_id))

@app.route('/analyze/<session_id>')
def analyze(session_id):
    """Analysis page - processes images and shows results"""
    
    if session_id not in sessions:
        flash('Session not found')
        return redirect(url_for('index'))
    
    return render_template('analysis.html', 
                         session_id=session_id, 
                         files=sessions[session_id]['uploaded_files'])

@app.route('/process/<session_id>')
def process_images(session_id):
    """API endpoint to process images with Claude - handles both single and multi-photo workflows"""

    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    session_data = sessions[session_id]
    flow_direction = normalize_flow_direction(session_data.get('flow_direction'))
    print(f"[process] session={session_id} flow_direction='{flow_direction}'")
    results = []

    try:
        # Check if this is a multi-photo session
        if session_data.get('multi_photo', False) and len(session_data['uploaded_files']) > 1:
            # Multi-photo workflow
            print("Processing multi-photo session...")

            # Separate overview and detail photos
            overview_file = None
            detail_files = []

            for file_info in session_data['uploaded_files']:
                if file_info.get('photo_type') == 'overview':
                    overview_file = file_info
                else:
                    detail_files.append(file_info)

            if not overview_file:
                return jsonify({'error': 'No overview photo found'}), 400

            # Extract paths
            overview_path = overview_file['filepath']
            detail_paths = [f['filepath'] for f in detail_files]

            # Process using multi-photo analyzer
            analysis = analyzer.process_multi_photo_session(
                overview_path,
                detail_paths,
                flow_direction
            )

            if analysis:
                results.append({
                    'filename': 'Multi-photo workflow',
                    'filepath': overview_path,
                    'analysis': analysis,
                    'status': 'success',
                    'multi_photo': True
                })
            else:
                results.append({
                    'filename': 'Multi-photo workflow',
                    'filepath': overview_path,
                    'analysis': None,
                    'status': 'failed',
                    'multi_photo': True
                })

        else:
            # Single photo workflow (legacy mode)
            print("Processing single-photo session...")

            for file_info in session_data['uploaded_files']:
                filepath = file_info['filepath']
                original_name = file_info['original_name']

                print(f"Processing: {original_name}")

                # Analyze with Claude (single photo mode)
                analysis = analyzer.analyze_workflow(filepath, flow_direction=flow_direction)

                if analysis:
                    results.append({
                        'filename': original_name,
                        'filepath': filepath,
                        'analysis': analysis,
                        'status': 'success',
                        'multi_photo': False
                    })
                else:
                    results.append({
                        'filename': original_name,
                        'filepath': filepath,
                        'analysis': None,
                        'status': 'failed',
                        'multi_photo': False
                    })

        # Store results in session
        sessions[session_id]['analysis_results'] = results
        sessions[session_id]['status'] = 'analyzed'

        return jsonify({
            'status': 'complete',
            'results': results,
            'total_processed': len(results),
            'successful': len([r for r in results if r['status'] == 'success'])
        })

    except Exception as e:
        import traceback
        print(f"Processing error: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/review/<session_id>')
def review(session_id):
    """Review page - show results and detect duplicates"""

    if session_id not in sessions:
        flash('Session not found')
        return redirect(url_for('index'))

    session_data = sessions[session_id]

    if session_data['status'] != 'analyzed':
        flash('Images not yet analyzed')
        return redirect(url_for('analyze', session_id=session_id))

    # Debug: Log what we're sending to the template
    if session_data['analysis_results']:
        first_result = session_data['analysis_results'][0]
        if first_result.get('analysis') and first_result['analysis'].get('sticky_notes'):
            notes = first_result['analysis']['sticky_notes']
            print(f"DEBUG: Sending {len(notes)} notes to review.html")
            for note in notes[:3]:  # Log first 3 notes
                print(f"  Note {note.get('id')}: text='{note.get('text', 'NO TEXT')[:50]}'")

    return render_template('review.html',
                         session_id=session_id,
                         results=session_data['analysis_results'])

@app.route('/save-edits/<session_id>', methods=['POST'])
def save_edits(session_id):
    """Save edited sticky note data and workflow sequence"""
    
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    try:
        edited_data = request.get_json()
        edited_notes = edited_data.get('editedNotes', {})
        deleted_notes = edited_data.get('deletedNotes', [])
        workflow_sequence = edited_data.get('workflowSequence', [])
        
        # Update the analysis results with edited data
        session_data = sessions[session_id]
        if 'analysis_results' in session_data:
            for result in session_data['analysis_results']:
                if result['status'] == 'success' and 'analysis' in result:
                    sticky_notes = result['analysis'].get('sticky_notes', [])
                    
                    # Remove deleted notes
                    deleted_note_ids = [int(nid) for nid in deleted_notes]
                    sticky_notes[:] = [note for note in sticky_notes if note.get('id') not in deleted_note_ids]
                    
                    # Clean up parallel relationships that reference deleted notes
                    for note in sticky_notes:
                        if note.get('parallel_with') in deleted_note_ids:
                            note['parallel_with'] = None
                    
                    # Apply edits to remaining notes
                    for note in sticky_notes:
                        note_id = str(note.get('id'))
                        if note_id in edited_notes:
                            edits = edited_notes[note_id]
                            note['text'] = edits.get('text', note.get('text'))
                            note['position'] = edits.get('position', note.get('position'))
                            note['color'] = edits.get('color', note.get('color'))
                            note['shape'] = edits.get('shape', note.get('shape'))
                            note['parallel_with'] = edits.get('parallel_with', note.get('parallel_with'))
                            note['decision_branches'] = edits.get('decision_branches', note.get('decision_branches'))
                    
                    # Remove deleted notes from workflow sequence and update if provided
                    if workflow_sequence:
                        # Filter out deleted notes from sequence
                        workflow_sequence = [nid for nid in workflow_sequence if nid not in deleted_note_ids]
                        result['analysis']['workflow_sequence'] = workflow_sequence
        
        return jsonify({'status': 'success', 'message': 'Edits and sequence saved successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect-readability/<session_id>')
def detect_readability(session_id):
    """Check if overview photo alone is sufficient (high-res, all text readable)"""

    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    session_data = sessions[session_id]

    # Get overview photo (should be first uploaded file)
    if not session_data.get('uploaded_files'):
        return jsonify({'error': 'No files uploaded'}), 404

    overview_file = session_data['uploaded_files'][0]
    overview_path = overview_file['filepath']

    try:
        # Analyze overview to check readability
        overview_result = analyzer.analyze_overview(overview_path)

        if not overview_result:
            return jsonify({'error': 'Overview analysis failed'}), 500

        total_count = len(overview_result.get('sticky_notes', []))
        readable_count = overview_result.get('readable_count', 0)
        readability_score = overview_result.get('readability_score', 0)

        # Consider sufficient if 80%+ text is readable
        sufficient = readability_score >= 0.8

        return jsonify({
            'sufficient': sufficient,
            'readable_count': readable_count,
            'total_count': total_count,
            'readability_score': readability_score,
            'message': f"{readable_count}/{total_count} notes readable ({readability_score:.1%})"
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/merge-notes/<session_id>', methods=['POST'])
def merge_notes(session_id):
    """Merge duplicate notes manually flagged by user"""

    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    try:
        merge_data = request.get_json()
        note_id_1 = merge_data.get('note_id_1')
        note_id_2 = merge_data.get('note_id_2')
        keep = merge_data.get('keep')  # Which note ID to keep

        if not all([note_id_1, note_id_2, keep]):
            return jsonify({'error': 'Missing required fields'}), 400

        session_data = sessions[session_id]

        # Find and merge notes in analysis results
        for result in session_data.get('analysis_results', []):
            if result['status'] == 'success' and 'sticky_notes' in result['analysis']:
                sticky_notes = result['analysis']['sticky_notes']

                note1 = next((n for n in sticky_notes if n['id'] == note_id_1), None)
                note2 = next((n for n in sticky_notes if n['id'] == note_id_2), None)

                if note1 and note2:
                    # Keep the selected note, remove the other
                    if keep == note_id_1:
                        sticky_notes[:] = [n for n in sticky_notes if n['id'] != note_id_2]
                    else:
                        sticky_notes[:] = [n for n in sticky_notes if n['id'] != note_id_1]

                    # Update workflow sequence
                    workflow_seq = result['analysis'].get('workflow_sequence', [])
                    if keep == note_id_1 and note_id_2 in workflow_seq:
                        workflow_seq.remove(note_id_2)
                    elif keep == note_id_2 and note_id_1 in workflow_seq:
                        workflow_seq.remove(note_id_1)

                    return jsonify({
                        'status': 'success',
                        'message': f'Notes merged, kept note {keep}'
                    })

        return jsonify({'error': 'Notes not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add-note/<session_id>', methods=['POST'])
def add_note(session_id):
    """Insert manually added note into sequence"""

    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    try:
        note_data = request.get_json()
        text = note_data.get('text', '')
        color = note_data.get('color', 'yellow')
        shape = note_data.get('shape', 'square')
        position_after = note_data.get('position_after')  # Note ID to insert after

        if not text:
            return jsonify({'error': 'Text is required'}), 400

        session_data = sessions[session_id]

        # Add note to analysis results
        for result in session_data.get('analysis_results', []):
            if result['status'] == 'success' and 'sticky_notes' in result['analysis']:
                sticky_notes = result['analysis']['sticky_notes']
                workflow_seq = result['analysis'].get('workflow_sequence', [])

                # Generate new note ID
                max_id = max([n['id'] for n in sticky_notes], default=0)
                new_id = max_id + 1

                new_note = {
                    'id': new_id,
                    'text': text,
                    'color': color,
                    'shape': shape,
                    'position': 'manual',
                    'source': 'manual',
                    'confidence': 100
                }

                sticky_notes.append(new_note)

                # Insert into workflow sequence
                if position_after and position_after in workflow_seq:
                    insert_index = workflow_seq.index(position_after) + 1
                    workflow_seq.insert(insert_index, new_id)
                else:
                    # Add to end if no position specified
                    workflow_seq.append(new_id)

                return jsonify({
                    'status': 'success',
                    'note': new_note,
                    'message': f'Note {new_id} added'
                })

        return jsonify({'error': 'No analysis results found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect-conflicts/<session_id>')
def detect_conflicts(session_id):
    """Find detail photo overlaps with different transcriptions"""

    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    session_data = sessions[session_id]

    # Check if multi-photo analysis was performed
    conflicts = []

    for result in session_data.get('analysis_results', []):
        if result['status'] == 'success' and 'analysis' in result:
            analysis = result['analysis']

            # Check if conflicts exist from multi-photo processing
            if 'conflicts' in analysis:
                conflicts = analysis['conflicts']

    return jsonify({
        'conflicts': conflicts,
        'count': len(conflicts)
    })

@app.route('/generate-pdf/<session_id>')
def generate_pdf(session_id):
    """Generate visual workflow diagram PDF"""
    print("=== GENERATE PDF ROUTE HIT ===")
    print(f"Session ID: {session_id}")
    
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session_data = sessions[session_id]
    
    if 'analysis_results' not in session_data or not session_data['analysis_results']:
        return jsonify({'error': 'No analysis results found'}), 404
    
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.pdfgen import canvas
        import os
        from datetime import datetime

        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"workflow_{session_id}_{timestamp}.pdf"
        pdf_path = os.path.join(OUTPUT_FOLDER, pdf_filename)

        page_width, page_height = letter
        flow_dir_session = normalize_flow_direction(session_data.get('flow_direction'))
        total_notes = 0
        for result in session_data['analysis_results']:
            if result.get('status') == 'success' and result.get('analysis'):
                analysis_r = result['analysis']
                # For vertical swim lanes the page height is driven by the TALLEST
                # lane (lanes render side-by-side, not stacked), so count only the
                # deepest lane rather than the total note count.
                if flow_dir_session == 'vertical-swim-lanes':
                    wf_meta = analysis_r.get('workflows', [])
                    if wf_meta:
                        total_notes += max(len(wf.get('note_ids', [])) for wf in wf_meta)
                        continue
                total_notes += (len(analysis_r.get('workflow_sequence', []))
                                or len(analysis_r.get('sticky_notes', [])))
        total_notes = max(total_notes, 1)
        required_height = max(page_height, total_notes * 150 + 300)
        custom_pagesize = (page_width, required_height)

        c = canvas.Canvas(pdf_path, pagesize=custom_pagesize)
        current_y_offset = required_height - 100

        for result in session_data['analysis_results']:
            if result['status'] == 'success' and result.get('analysis'):
                analysis = result['analysis']
                workflow_sequence = analysis.get('workflow_sequence', [])
                sticky_notes = analysis.get('sticky_notes', [])
                swim_lanes = analysis.get('swim_lanes', [])
                workflow_metadata = analysis.get('workflows', [])   # T3.0
                process_title = analysis.get('process_title')       # T3.0

                if workflow_sequence and sticky_notes:
                    flow_dir = analysis.get('flow_direction', '')
                    print(f"[generate_pdf] notes={len(sticky_notes)} seq={len(workflow_sequence)} "
                          f"lanes={len(workflow_metadata)} flow_dir='{flow_dir}' "
                          f"swim_lanes={len(swim_lanes)} title='{process_title}'")

                    # T3.0: Render process title (Tier 1 banner) above all lanes
                    if process_title:
                        c.saveState()
                        c.setFont("Helvetica-Bold", 14)
                        c.setFillColor(colors.black)
                        title_width = c.stringWidth(process_title, "Helvetica-Bold", 14)
                        c.drawString(
                            (page_width - title_width) / 2,
                            current_y_offset,
                            process_title
                        )
                        c.restoreState()
                        current_y_offset -= 26   # 14pt font + 12pt gap

                    # Check if swim lanes were detected
                    if swim_lanes and len(swim_lanes) > 1:
                        # Multi-lane workflow - generate separate sections for each lane
                        print(f"Generating PDF with {len(swim_lanes)} swim lanes...")

                        for i, lane in enumerate(swim_lanes):
                            # Draw lane header
                            c.saveState()
                            c.setFont("Helvetica-Bold", 16)
                            c.setFillColor(colors.HexColor('#007bff'))
                            header_text = f"Lane {i+1}: {lane['header'].get('text', 'Unnamed Lane')}"
                            c.drawString(50, current_y_offset, header_text)
                            c.restoreState()

                            current_y_offset -= 40

                            # Get notes for this lane
                            lane_note_ids = lane['notes']
                            lane_notes = [n for n in sticky_notes if n['id'] in lane_note_ids]

                            # Create sequence for this lane only
                            lane_sequence = [n['id'] for n in lane_notes]

                            if lane_sequence and lane_notes:
                                # Create and draw process map for this lane
                                process_map = ProcessMapFlowable(lane_notes, lane_sequence)
                                process_map.canv = c

                                # Save canvas state and translate for positioning
                                c.saveState()
                                c.translate(0, current_y_offset - process_map.height)

                                # Draw the flowable
                                process_map.draw()

                                # Restore canvas state
                                c.restoreState()

                                current_y_offset -= (process_map.height + 60)

                    elif workflow_metadata and len(workflow_metadata) > 1:
                        # T3.0: layout-strategy swim lanes
                        flow_dir = analysis.get('flow_direction', '')
                        notes_dict = {n['id']: n for n in sticky_notes}

                        if flow_dir == 'vertical-swim-lanes':
                            # Render lanes SIDE-BY-SIDE so the PDF mirrors the
                            # physical wall: each column gets an equal slice of
                            # the page width and all columns start at the same Y.
                            num_lanes   = len(workflow_metadata)
                            lane_margin = 30        # pts inside each page edge
                            col_width   = (page_width - 2 * lane_margin) / num_lanes

                            # Build all flowables first so we can align them to
                            # the tallest lane's height before translating.
                            lane_flowables = []
                            for wf in workflow_metadata:
                                lane_label    = wf.get('lane_label')
                                lane_note_ids = wf.get('note_ids', [])
                                lane_notes    = [notes_dict[nid] for nid in lane_note_ids
                                                 if nid in notes_dict]
                                lane_sequence = [n['id'] for n in lane_notes]
                                if lane_sequence and lane_notes:
                                    pm = ProcessMapFlowable(
                                        lane_notes, lane_sequence,
                                        width=col_width, lane_label=lane_label
                                    )
                                    lane_flowables.append((pm, wf))

                            if lane_flowables:
                                tallest = max(pm.height for pm, _ in lane_flowables)
                                for col_idx, (pm, _) in enumerate(lane_flowables):
                                    x_offset = lane_margin + col_idx * col_width
                                    pm.canv = c
                                    c.saveState()
                                    # Translate each lane by its OWN height so that
                                    # all columns are top-aligned (first note at the
                                    # same page Y regardless of lane depth).
                                    # Using `tallest` for all lanes would bottom-align
                                    # them, causing shorter columns to start lower.
                                    c.translate(x_offset, current_y_offset - pm.height)
                                    pm.draw()
                                    c.restoreState()
                                # Advance past the TALLEST column so the next section
                                # doesn't overlap the deepest lane.
                                current_y_offset -= (tallest + 60)

                        else:
                            # Horizontal swim lanes (or any other multi-lane type):
                            # stack each lane vertically at full page width.
                            for wf in workflow_metadata:
                                lane_label    = wf.get('lane_label')
                                lane_note_ids = wf.get('note_ids', [])
                                lane_notes    = [notes_dict[nid] for nid in lane_note_ids
                                                 if nid in notes_dict]
                                lane_sequence = [n['id'] for n in lane_notes]

                                if lane_sequence and lane_notes:
                                    process_map = ProcessMapFlowable(
                                        lane_notes, lane_sequence,
                                        lane_label=lane_label
                                    )
                                    process_map.canv = c
                                    c.saveState()
                                    c.translate(0, current_y_offset - process_map.height)
                                    process_map.draw()
                                    c.restoreState()
                                    current_y_offset -= (process_map.height + 60)

                    else:
                        # Single workflow or no swim lanes detected
                        # Create and draw process map
                        process_map = ProcessMapFlowable(sticky_notes, workflow_sequence)
                        process_map.canv = c

                        # Save canvas state and translate for positioning
                        c.saveState()
                        c.translate(0, current_y_offset - process_map.height)

                        # Draw the flowable
                        process_map.draw()

                        # Restore canvas state
                        c.restoreState()

                        current_y_offset -= (process_map.height + 100)
        
        # Save PDF
        c.save()
        
        return jsonify({
            'status': 'success',
            'filename': pdf_filename,
            'path': pdf_path,
            'message': f'Visual workflow PDF generated: {pdf_filename}'
        })
        
    except Exception as e:
        import traceback
        print(f"PDF generation error: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/cleanup')
def cleanup():
    """Clean up old sessions and files"""
    # Implementation for cleaning old files
    return jsonify({'status': 'Cleanup complete'})

if __name__ == '__main__':
    print("Starting Sticky Note Processor Web App...")
    print("Open browser to: http://localhost:5000")
    print("Upload folder:", os.path.abspath(UPLOAD_FOLDER))
    print("Output folder:", os.path.abspath(OUTPUT_FOLDER))
    print("Press Ctrl+C to stop")
    app.run(debug=True, port=5000)

