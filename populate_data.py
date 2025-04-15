import os
import django
import random
from datetime import datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetable_project.settings')
django.setup()

from exams.models import Course, Student, ExamHall

# Create departments
departments = ['Computer Science', 'Electrical Engineering', 'Mechanical Engineering', 'Mathematics']

# Create courses
courses_data = [
    # Computer Science
    ('CS101', 'Introduction to Programming', 1, 'Computer Science'),
    ('CS102', 'Data Structures', 1, 'Computer Science'),
    ('CS201', 'Database Systems', 2, 'Computer Science'),
    ('CS202', 'Computer Networks', 2, 'Computer Science'),
    ('CS301', 'Web Development', 3, 'Computer Science'),
    ('CS302', 'Data Science', 3, 'Computer Science'),
    # Electrical Engineering
    ('EE101', 'Circuit Theory', 1, 'Electrical Engineering'),
    ('EE102', 'Digital Electronics', 1, 'Electrical Engineering'),
    ('EE201', 'Analog Electronics', 2, 'Electrical Engineering'),
    ('EE202', 'Control Systems', 2, 'Electrical Engineering'),
    # Mechanical Engineering
    ('ME101', 'Engineering Mechanics', 1, 'Mechanical Engineering'),
    ('ME102', 'Thermodynamics', 1, 'Mechanical Engineering'),
    ('ME201', 'Fluid Mechanics', 2, 'Mechanical Engineering'),
    # Mathematics
    ('MATH101', 'Calculus I', 1, 'Mathematics'),
    ('MATH102', 'Linear Algebra', 1, 'Mathematics'),
    ('MATH201', 'Probability & Statistics', 2, 'Mathematics'),
]

# Create exam halls
halls_data = [
    ('Hall A', 120),
    ('Hall B', 100),
    ('Hall C', 150),
    ('Conference Room', 60),
]

def populate_data():
    # Create courses
    courses = []
    for code, name, semester, department in courses_data:
        course, created = Course.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'semester': semester,
                'department': department
            }
        )
        courses.append(course)
        if created:
            print(f"Created course: {course}")
        else:
            print(f"Course already exists: {course}")
    
    # Create halls
    for name, capacity in halls_data:
        hall, created = ExamHall.objects.get_or_create(
            name=name,
            defaults={'capacity': capacity}
        )
        if created:
            print(f"Created hall: {hall}")
        else:
            print(f"Hall already exists: {hall}")
    
    # Create students
    for dept in departments:
        for semester in [1, 2, 3]:
            # Create 20 students per dept/semester
            for i in range(1, 21):
                roll_number = f"{dept[:2]}{semester}{i:02d}"
                name = f"Student {roll_number}"
                
                student, created = Student.objects.get_or_create(
                    roll_number=roll_number,
                    defaults={
                        'name': name,
                        'semester': semester,
                        'department': dept
                    }
                )
                
                if created:
                    print(f"Created student: {student}")
                    
                    # Assign courses to student
                    dept_courses = [c for c in courses if c.department == dept and c.semester == semester]
                    # Also add some common courses like math
                    common_courses = [c for c in courses if c.department == 'Mathematics' and c.semester == semester]
                    
                    # Combine and select random subset of courses
                    available_courses = dept_courses + common_courses
                    selected_courses = random.sample(available_courses, min(len(available_courses), 5))
                    
                    student.courses.set(selected_courses)
                else:
                    print(f"Student already exists: {student}")

if __name__ == '__main__':
    print("Starting population script...")
    populate_data()
    print("Population complete!") 