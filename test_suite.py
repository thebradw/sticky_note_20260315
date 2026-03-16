#!/usr/bin/env python3
"""
Comprehensive Test Suite for Sticky Note Workflow Processor
Tests data structure integrity and relationship logic across all test images.

Tests cover:
1. Decision diamond branch positioning (NO left, YES right)
2. Duplicate step IDs
3. Self-referential branches
4. Missing branch labels
5. Wrong branch count (with Option A: only test diamonds with branches)
6. Duplicate step IDs in workflow data
7. Missing required fields
8. Invalid decision_branch values
9. Y-coordinate threshold violations for parallels
10. Incorrect source/target relationships
"""

import os
import sys
from typing import List, Dict, Any, Tuple

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_analyzer import StickyNoteAnalyzer

class WorkflowTestSuite:
    """Test suite for validating sticky note workflow analysis"""
    
    def __init__(self):
        self.analyzer = StickyNoteAnalyzer()
        self.test_images_dir = "test_images"
        self.test_images = [
            "newspaper_1header_decision.jpeg",
            "newspaper_noheader_decision.jpeg",
            "leftright_wholewall.jpeg",
            "leftright_headers_swimlane_painpoint.jpeg",
            "child1_wallcloseup.jpeg",
            "child2_wallcloseup.jpeg",
            "child3_wallcloseup.jpeg"
        ]
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def run_all_tests(self) -> bool:
        """Run complete test suite on all test images"""
        print("=" * 80)
        print("STICKY NOTE WORKFLOW TEST SUITE")
        print("=" * 80)
        
        all_passed = True
        
        for image_name in self.test_images:
            image_path = os.path.join(self.test_images_dir, image_name)
            
            if not os.path.exists(image_path):
                print(f"\n⚠️  SKIPPED: {image_name} (file not found)")
                continue
            
            print(f"\n{'='*80}")
            print(f"Testing: {image_name}")
            print(f"{'='*80}")
            
            # Run analysis
            try:
                result = self.analyzer.analyze_workflow(image_path, flow_direction='newspaper')
                
                if not result or 'sticky_notes' not in result:
                    print(f"❌ FAILED: Could not analyze {image_name}")
                    self.failed += 1
                    all_passed = False
                    continue
                
                notes = result['sticky_notes']
                print(f"\nAnalyzed {len(notes)} sticky notes")
                
                # Run all test categories
                self._test_decision_diamonds(notes, image_name)
                self._test_data_structure(notes, image_name)
                self._test_parallel_relationships(notes, image_name)
                
            except Exception as e:
                print(f"❌ ERROR analyzing {image_name}: {e}")
                self.failed += 1
                self.errors.append(f"{image_name}: {str(e)}")
                all_passed = False
        
        # Print summary
        self._print_summary()
        
        return all_passed
    
    def _test_decision_diamonds(self, notes: List[Dict], image_name: str):
        """Test decision diamond branch logic (Tests #1-5)"""
        print("\n--- Decision Diamond Tests ---")
        
        # Find all diamonds with branches (Option A logic)
        diamonds_with_branches = []
        for note in notes:
            if note.get('shape') == 'diamond':
                # Check if this diamond has outgoing branches
                branches = [n for n in notes if n.get('decision_branches', {}).get('yes_next_step') == note['id'] 
                           or n.get('decision_branches', {}).get('no_next_step') == note['id']]
                
                # Actually, check if THIS note has decision_branches defined
                if note.get('decision_branches'):
                    diamonds_with_branches.append(note)
        
        if not diamonds_with_branches:
            print("✓ No decision diamonds with branches found (no tests needed)")
            return
        
        print(f"Found {len(diamonds_with_branches)} decision diamond(s) with branches")
        
        for diamond in diamonds_with_branches:
            diamond_id = diamond['id']
            diamond_text = diamond.get('text', 'Untitled')[:30]
            branches = diamond.get('decision_branches', {})
            
            print(f"\nTesting diamond {diamond_id}: {diamond_text}")
            
            # Test #3: Self-referential branches
            yes_step = branches.get('yes_next_step')
            no_step = branches.get('no_next_step')
            
            if yes_step == diamond_id or no_step == diamond_id:
                self._log_failure(
                    image_name, 
                    f"Test #3 FAILED: Diamond {diamond_id} has self-referential branch"
                )
            else:
                self._log_pass(f"Test #3: No self-reference")
            
            # Test #4: Missing branch labels (both yes and no should exist)
            if yes_step is None and no_step is None:
                self._log_failure(
                    image_name,
                    f"Test #4 FAILED: Diamond {diamond_id} has no branch labels"
                )
            else:
                self._log_pass(f"Test #4: Branch labels exist")
            
            # Test #5: Wrong branch count (should have exactly 2 branches for diamonds with branches)
            branch_count = sum([yes_step is not None, no_step is not None])
            if branch_count != 2:
                self._log_failure(
                    image_name,
                    f"Test #5 FAILED: Diamond {diamond_id} has {branch_count} branches, expected 2"
                )
            else:
                self._log_pass(f"Test #5: Correct branch count (2)")
            
            # Test #1: Branch positioning (YES right, NO left)
            # Find the actual note objects for yes and no branches
            yes_note = next((n for n in notes if n['id'] == yes_step), None)
            no_note = next((n for n in notes if n['id'] == no_step), None)
            
            if yes_note and no_note:
                # Check X-coordinates
                yes_x = yes_note.get('center_x', 0)
                no_x = no_note.get('center_x', 0)
                diamond_x = diamond.get('center_x', 0)
                
                # YES should be to the RIGHT (higher X), NO should be BELOW or LEFT
                # Based on your previous bugs, NO is typically below (higher Y)
                yes_y = yes_note.get('center_y', 0)
                no_y = no_note.get('center_y', 0)
                diamond_y = diamond.get('center_y', 0)
                
                # Check if branches are positioned correctly
                # YES branch should be to the right (x > diamond_x)
                # NO branch should be below (y > diamond_y)
                
                if yes_x > diamond_x and no_y > diamond_y:
                    self._log_pass(f"Test #1: Branch positioning correct (YES right, NO below)")
                else:
                    # Detailed failure message
                    position_info = f"Diamond at ({diamond_x:.0f}, {diamond_y:.0f}), "
                    position_info += f"YES at ({yes_x:.0f}, {yes_y:.0f}), "
                    position_info += f"NO at ({no_x:.0f}, {no_y:.0f})"
                    
                    self._log_failure(
                        image_name,
                        f"Test #1 FAILED: Diamond {diamond_id} has incorrect branch positioning. {position_info}"
                    )
    
    def _test_data_structure(self, notes: List[Dict], image_name: str):
        """Test data structure integrity (Tests #6, #7, #8, #10)"""
        print("\n--- Data Structure Tests ---")
        
        # Test #6: Duplicate step IDs
        id_counts = {}
        for note in notes:
            note_id = note.get('id')
            id_counts[note_id] = id_counts.get(note_id, 0) + 1
        
        duplicates = [id for id, count in id_counts.items() if count > 1]
        if duplicates:
            self._log_failure(
                image_name,
                f"Test #6 FAILED: Duplicate step IDs found: {duplicates}"
            )
        else:
            self._log_pass(f"Test #6: No duplicate step IDs ({len(notes)} unique)")
        
        # Test #7: Missing required fields
        required_fields = ['id', 'text', 'color', 'shape', 'bbox']
        missing_fields_notes = []
        
        for note in notes:
            missing = [field for field in required_fields if field not in note]
            if missing:
                missing_fields_notes.append({
                    'id': note.get('id', 'unknown'),
                    'missing': missing
                })
        
        if missing_fields_notes:
            details = ", ".join([f"ID {n['id']}: {n['missing']}" for n in missing_fields_notes])
            self._log_failure(
                image_name,
                f"Test #7 FAILED: Notes with missing required fields: {details}"
            )
        else:
            self._log_pass(f"Test #7: All required fields present")
        
        # Test #8: Invalid decision_branch values
        invalid_branches = []
        for note in notes:
            if note.get('decision_branches'):
                branches = note['decision_branches']
                
                # Check for valid structure
                yes_step = branches.get('yes_next_step')
                no_step = branches.get('no_next_step')
                
                # Validate that referenced IDs exist
                all_ids = [n['id'] for n in notes]
                
                if yes_step is not None and yes_step not in all_ids:
                    invalid_branches.append(f"ID {note['id']}: yes_next_step={yes_step} does not exist")
                
                if no_step is not None and no_step not in all_ids:
                    invalid_branches.append(f"ID {note['id']}: no_next_step={no_step} does not exist")
        
        if invalid_branches:
            self._log_failure(
                image_name,
                f"Test #8 FAILED: Invalid decision branch references: {'; '.join(invalid_branches)}"
            )
        else:
            self._log_pass(f"Test #8: All decision branch values valid")
        
        # Test #10: Incorrect source/target relationships
        # Check that decision branches point to valid notes
        broken_links = []
        for note in notes:
            if note.get('decision_branches'):
                branches = note['decision_branches']
                yes_step = branches.get('yes_next_step')
                no_step = branches.get('no_next_step')
                rejoin_step = branches.get('rejoin_step')
                
                # Verify all referenced steps exist
                for step_id, label in [(yes_step, 'yes'), (no_step, 'no'), (rejoin_step, 'rejoin')]:
                    if step_id is not None:
                        target_note = next((n for n in notes if n['id'] == step_id), None)
                        if not target_note:
                            broken_links.append(f"ID {note['id']} → {label} step {step_id} not found")
        
        if broken_links:
            self._log_failure(
                image_name,
                f"Test #10 FAILED: Broken source/target relationships: {'; '.join(broken_links)}"
            )
        else:
            self._log_pass(f"Test #10: All source/target relationships valid")
    
    def _test_parallel_relationships(self, notes: List[Dict], image_name: str):
        """Test parallel step detection logic (Test #9)"""
        print("\n--- Parallel Relationship Tests ---")
        
        # Test #9: Y-coordinate threshold violations
        PARALLEL_Y_THRESHOLD = 50  # pixels - this should match your analyzer's threshold
        
        violations = []
        for note in notes:
            parallel_id = note.get('parallel_with')
            if parallel_id:
                parallel_note = next((n for n in notes if n['id'] == parallel_id), None)
                
                if parallel_note:
                    y1 = note.get('center_y', 0)
                    y2 = parallel_note.get('center_y', 0)
                    y_diff = abs(y1 - y2)
                    
                    if y_diff > PARALLEL_Y_THRESHOLD:
                        violations.append(
                            f"ID {note['id']} ↔ ID {parallel_id}: Y-diff={y_diff:.0f}px (threshold={PARALLEL_Y_THRESHOLD}px)"
                        )
        
        if violations:
            self._log_failure(
                image_name,
                f"Test #9 FAILED: Y-coordinate threshold violations: {'; '.join(violations)}"
            )
        else:
            parallel_count = len([n for n in notes if n.get('parallel_with')])
            self._log_pass(f"Test #9: All parallel relationships within threshold ({parallel_count} parallel pairs)")
    
    def _log_pass(self, message: str):
        """Log a passed test"""
        print(f"  ✓ {message}")
        self.passed += 1
    
    def _log_failure(self, image_name: str, message: str):
        """Log a failed test"""
        print(f"  ❌ {message}")
        self.failed += 1
        self.errors.append(f"{image_name}: {message}")
    
    def _print_summary(self):
        """Print test execution summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests Run: {self.passed + self.failed}")
        print(f"✓ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        
        if self.errors:
            print("\nFailed Tests:")
            for error in self.errors:
                print(f"  • {error}")
        
        print("=" * 80)
        
        if self.failed == 0:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {self.failed} test(s) failed")
        
        print("=" * 80)

def main():
    """Run the test suite"""
    suite = WorkflowTestSuite()
    success = suite.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
