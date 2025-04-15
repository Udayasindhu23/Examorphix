from datetime import datetime, timedelta
from .models import Course, Student, ExamHall, Timetable, Exam

def generate_timetable(name, courses, start_date, end_date, exam_slots_per_day=2, duration_hours=3):
    """
    Generate an exam timetable.
    
    Args:
        name: Name for the timetable
        courses: List of Course objects to schedule
        start_date: First day of exams
        end_date: Last day of exams
        exam_slots_per_day: Number of exam slots per day (default: 2)
        duration_hours: Duration of each exam in hours (default: 3)
    
    Returns:
        A new Timetable object
    """
    # Create a new timetable
    timetable = Timetable.objects.create(
        name=name,
        start_date=start_date,
        end_date=end_date
    )
    
    # Create a list of available dates
    current_date = start_date
    available_dates = []
    while current_date <= end_date:
        available_dates.append(current_date)
        current_date += timedelta(days=1)
    
    # Define exam time slots
    time_slots = []
    if exam_slots_per_day >= 1:
        time_slots.append({"start": datetime.strptime("09:00", "%H:%M").time(),
                          "end": datetime.strptime(f"{9+duration_hours}:00", "%H:%M").time()})
    if exam_slots_per_day >= 2:
        time_slots.append({"start": datetime.strptime("14:00", "%H:%M").time(),
                          "end": datetime.strptime(f"{14+duration_hours}:00", "%H:%M").time()})
    
    # Find exam halls
    halls = ExamHall.objects.all()
    if not halls:
        # Create a default hall if none exists
        halls = [ExamHall.objects.create(name="Main Hall", capacity=200)]
    
    # Create a conflict matrix (courses that can't be scheduled at the same time)
    conflicts = {}
    for course in courses:
        conflicts[course.id] = set()
        # Get all students taking this course
        students_in_course = Student.objects.filter(courses=course)
        
        # Find other courses these students are taking
        for student in students_in_course:
            for other_course in student.courses.all():
                if other_course.id != course.id:
                    conflicts[course.id].add(other_course.id)
    
    # Sort courses by number of conflicts (most constrained first)
    courses_to_schedule = sorted(courses, key=lambda c: len(conflicts[c.id]), reverse=True)
    
    # Schedule exams
    schedule = {}  # (date, time_slot_index) -> [course_ids]
    course_assignments = {}  # course_id -> (date, time_slot_index)
    
    for course in courses_to_schedule:
        # Try to find a suitable slot
        scheduled = False
        
        # Prioritize dates first, then time slots
        for date in available_dates:
            for slot_index, time_slot in enumerate(time_slots):
                key = (date, slot_index)
                
                # Initialize the slot if not exists
                if key not in schedule:
                    schedule[key] = []
                
                # Check if this course conflicts with any course already in this slot
                has_conflict = False
                for scheduled_course_id in schedule[key]:
                    if scheduled_course_id in conflicts[course.id]:
                        has_conflict = True
                        break
                
                if not has_conflict:
                    # Schedule the course in this slot
                    schedule[key].append(course.id)
                    course_assignments[course.id] = key
                    scheduled = True
                    break
            
            if scheduled:
                break
        
        # If we couldn't schedule, put it in a new slot
        if not scheduled:
            # Try to add to the least populated slot
            min_conflicts = float('inf')
            best_slot = None
            
            for date in available_dates:
                for slot_index, time_slot in enumerate(time_slots):
                    key = (date, slot_index)
                    
                    # Initialize the slot if not exists
                    if key not in schedule:
                        schedule[key] = []
                    
                    # Count conflicts
                    conflict_count = 0
                    for scheduled_course_id in schedule[key]:
                        if scheduled_course_id in conflicts[course.id]:
                            conflict_count += 1
                    
                    if conflict_count < min_conflicts:
                        min_conflicts = conflict_count
                        best_slot = key
            
            # Schedule in the best slot
            if best_slot:
                schedule[best_slot].append(course.id)
                course_assignments[course.id] = best_slot
    
    # Create Exam objects for each scheduled course
    for course_id, (date, slot_index) in course_assignments.items():
        course = Course.objects.get(id=course_id)
        time_slot = time_slots[slot_index]
        hall = halls[0]  # Simple allocation - just use the first hall for now
        
        Exam.objects.create(
            timetable=timetable,
            course=course,
            date=date,
            start_time=time_slot["start"],
            end_time=time_slot["end"],
            hall=hall
        )
    
    return timetable 