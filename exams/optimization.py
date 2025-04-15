from typing import List, Dict, Tuple
import numpy as np
from datetime import datetime, timedelta
from .models import Student, Exam, Classroom, Invigilator, SeatAllocation

def knapsack_seat_allocation(students: List[Student], classroom: Classroom, social_distance: int = 1, initial_grid: np.ndarray = None) -> List[Tuple[int, int]]:
    """
    Allocate seats using a knapsack-like approach with social distancing constraints.
    
    Args:
        students: List of students to allocate seats for
        classroom: The classroom to allocate seats in
        social_distance: Minimum distance between students (in seats)
        initial_grid: Optional pre-existing grid with occupied seats marked as True
    
    Returns:
        List of (row, column) tuples representing seat allocations
    """
    # Calculate classroom dimensions
    rows = int(np.sqrt(classroom.capacity))
    cols = classroom.capacity // rows
    
    # Create a grid to track occupied seats
    if initial_grid is not None and initial_grid.shape == (rows, cols):
        grid = initial_grid.copy()
    else:
        grid = np.zeros((rows, cols), dtype=bool)
    
    # List to store seat allocations
    allocations = []
    
    def is_valid_position(row: int, col: int, distance: int) -> bool:
        """Check if a position is valid with given social distance"""
        if grid[row, col]:
            return False
            
        # Check surrounding seats within social distance (in a zigzag pattern)
        for r in range(max(0, row - distance), min(rows, row + distance + 1)):
            for c in range(max(0, col - distance), min(cols, col + distance + 1)):
                if grid[r, c]:
                    # Calculate Manhattan distance
                    manhattan_dist = abs(row - r) + abs(col - c)
                    if manhattan_dist <= distance:
                        return False
        return True
    
    def get_next_position(current_row: int, current_col: int, distance: int) -> Tuple[int, int]:
        """Get the next position based on the current position and social distance"""
        next_col = current_col + distance + 1
        next_row = current_row
        
        # If we reach the end of the row, move to next row
        if next_col >= cols:
            next_col = 0
            next_row = current_row + 1
            # If on even row, start from beginning; if on odd row, start with offset
            if next_row % 2 == 1:
                next_col = min(1, cols - 1)
        
        return next_row, next_col
    
    # Start allocation from the first position
    current_row = 0
    current_col = 0
    
    for student in students:
        seat_found = False
        attempts = 0
        max_attempts = rows * cols  # Prevent infinite loop
        
        while not seat_found and attempts < max_attempts:
            if current_row < rows and is_valid_position(current_row, current_col, social_distance):
                grid[current_row, current_col] = True
                allocations.append((current_row, current_col))
                seat_found = True
            
            # Get next position in zigzag pattern
            current_row, current_col = get_next_position(current_row, current_col, social_distance)
            
            # If we reach the end of the grid, try with reduced distance
            if current_row >= rows:
                if social_distance > 0:
                    social_distance -= 1
                    current_row = 0
                    current_col = 0
                else:
                    break
            
            attempts += 1
    
    return allocations

def branch_and_bound_invigilator_assignment(exams: List[Exam], invigilators: List[Invigilator]) -> Dict[int, List[int]]:
    """
    Assign invigilators to exams using branch and bound algorithm.
    
    Args:
        exams: List of exams to assign invigilators to
        invigilators: List of available invigilators
    
    Returns:
        Dictionary mapping exam IDs to lists of assigned invigilator IDs
    """
    # Initialize best solution
    best_solution = {}
    best_score = float('inf')
    
    def calculate_score(assignment: Dict[int, List[int]]) -> float:
        """Calculate the score for an assignment (lower is better)"""
        score = 0
        invigilator_hours = {inv.id: 0 for inv in invigilators}
        
        for exam_id, inv_ids in assignment.items():
            exam = next(e for e in exams if e.id == exam_id)
            duration = (datetime.combine(datetime.today(), exam.end_time) - 
                       datetime.combine(datetime.today(), exam.start_time)).total_seconds() / 3600
            
            for inv_id in inv_ids:
                invigilator_hours[inv_id] += duration
        
        # Penalize overworked invigilators
        for inv in invigilators:
            if invigilator_hours[inv.id] > inv.max_hours_per_day:
                score += (invigilator_hours[inv.id] - inv.max_hours_per_day) ** 2
        
        return score
    
    def branch_and_bound(current_assignment: Dict[int, List[int]], remaining_exams: List[Exam]):
        nonlocal best_solution, best_score
        
        if not remaining_exams:
            current_score = calculate_score(current_assignment)
            if current_score < best_score:
                best_score = current_score
                best_solution = current_assignment.copy()
            return
        
        exam = remaining_exams[0]
        remaining_exams = remaining_exams[1:]
        
        # Try assigning different combinations of invigilators
        for i in range(len(invigilators)):
            for j in range(i + 1, len(invigilators)):
                new_assignment = current_assignment.copy()
                new_assignment[exam.id] = [invigilators[i].id, invigilators[j].id]
                
                # Prune if the current score is worse than the best
                if calculate_score(new_assignment) >= best_score:
                    continue
                
                branch_and_bound(new_assignment, remaining_exams)
    
    # Start the branch and bound algorithm
    branch_and_bound({}, exams)
    return best_solution

def generate_heatmap(seat_allocations: List[SeatAllocation], rows: int, cols: int) -> np.ndarray:
    """
    Generate a heatmap of seat allocations.
    
    Args:
        seat_allocations: List of seat allocations
        rows: Number of rows in the classroom
        cols: Number of columns in the classroom
    
    Returns:
        Numpy array representing the heatmap
    """
    heatmap = np.zeros((rows, cols))
    
    for allocation in seat_allocations:
        heatmap[allocation.row, allocation.column] = 1
    
    return heatmap 