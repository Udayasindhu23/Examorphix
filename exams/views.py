from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from datetime import datetime, timedelta
import csv
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.decorators import login_required
import numpy as np
from django.db.utils import IntegrityError
import random

from .models import Course, Student, ExamHall, Timetable, Exam, Department, Classroom, SeatAllocation, Invigilator, Attendance
from .timetable_generator import generate_timetable
from .optimization import (
    knapsack_seat_allocation,
    branch_and_bound_invigilator_assignment,
    generate_heatmap
)

def welcome(request):
    return render(request, 'exams/welcome.html')

def home(request):
    return render(request, 'exams/home.html', {
        'timetables': Timetable.objects.all().order_by('-created_at')
    })

def dashboard(request):
    """Redirect to home page"""
    return redirect('home')

def timetable_form(request):
    courses = Course.objects.all()
    return render(request, 'exams/timetable_form.html', {'courses': courses})

def create_timetable(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        year = request.POST.get('year')
        department_ids = request.POST.getlist('department_ids')
        course_ids = request.POST.getlist('course_ids')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        # Validate required fields
        if not all([name, year, department_ids, course_ids, start_date, end_date]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('create_timetable')

        try:
            # Convert dates
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

            # Validate dates
            if start_date >= end_date:
                messages.error(request, 'End date must be after start date.')
                return redirect('create_timetable')

            # Get departments and courses
            departments = Department.objects.filter(id__in=department_ids)
            courses = Course.objects.filter(id__in=course_ids)

            # Create timetable
            timetable = Timetable.objects.create(
                name=name,
                year=year,
                start_date=start_date,
                end_date=end_date
            )

            # Add departments and courses
            timetable.departments.set(departments)
            timetable.courses.set(courses)

            messages.success(request, f'Timetable "{name}" created successfully!')
            return redirect('view_timetable', timetable.id)

        except Exception as e:
            messages.error(request, f'Error creating timetable: {str(e)}')
            return redirect('create_timetable')

    # GET request - show form
    departments = Department.objects.all()
    courses = Course.objects.all()
    return render(request, 'exams/create_timetable.html', {
        'departments': departments,
        'courses': courses
    })

def view_timetable(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    exams = Exam.objects.filter(timetable=timetable).select_related('course', 'course__department', 'hall').order_by('date', 'start_time')
    
    # Organize exams by date
    exams_by_date = {}
    for exam in exams:
        date_str = exam.date.strftime('%Y-%m-%d')  # Use consistent date format as key
        if date_str not in exams_by_date:
            exams_by_date[date_str] = []
        exams_by_date[date_str].append(exam)
    
    # Sort the dates
    sorted_dates = sorted(exams_by_date.keys())
    sorted_exams_by_date = {date: exams_by_date[date] for date in sorted_dates}
    
    return render(request, 'exams/view_timetable.html', {
        'timetable': timetable,
        'exams_by_date': sorted_exams_by_date
    })

def export_timetable(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    
    # Get all exams for this timetable and organize by date
    exams = timetable.exams.all().order_by('date', 'start_time')
    exams_by_date = {}
    for exam in exams:
        date_str = exam.date.strftime('%Y-%m-%d')
        if date_str not in exams_by_date:
            exams_by_date[date_str] = []
        exams_by_date[date_str].append(exam)
    
    context = {
        'timetable': timetable,
        'exams_by_date': exams_by_date,
        'current_date': timezone.now().date(),
    }
    
    # Render the template
    html = render(request, 'exams/timetable_pdf.html', context).content
    
    # Create PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{timetable.name}_timetable.pdf"'
        return response
    
    return HttpResponse('Error generating PDF', status=500)

def subject_schedule(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    courses = Course.objects.filter(exam__timetable=timetable).distinct()
    exams = Exam.objects.filter(timetable=timetable).order_by('date', 'start_time')
    
    # Organize data by course
    course_schedule = {}
    for course in courses:
        course_exams = exams.filter(course=course)
        if course_exams:
            course_schedule[course] = course_exams.first()
    
    # Get all dates in the timetable for the header
    all_dates = exams.values_list('date', flat=True).distinct().order_by('date')
    
    # Get all time slots
    time_slots = set()
    for exam in exams:
        time_slots.add((exam.start_time, exam.end_time))
    time_slots = sorted(list(time_slots))
    
    return render(request, 'exams/subject_schedule.html', {
        'timetable': timetable,
        'course_schedule': course_schedule,
        'all_dates': all_dates,
        'time_slots': time_slots
    })

def create_empty_timetable(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        year = request.POST.get('year')
        department_ids = request.POST.getlist('department_ids')
        course_ids = request.POST.getlist('course_ids')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        # Validate required fields
        if not all([name, year, start_date, end_date]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('create_timetable')

        try:
            # Convert dates
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

            # Validate dates
            if start_date >= end_date:
                messages.error(request, 'End date must be after start date.')
                return redirect('create_timetable')

            # Create timetable
            timetable = Timetable.objects.create(
                name=name,
                year=year,
                start_date=start_date,
                end_date=end_date
            )

            # Add departments and courses if selected
            if department_ids:
                departments = Department.objects.filter(id__in=department_ids)
                timetable.departments.set(departments)
            
            if course_ids:
                courses = Course.objects.filter(id__in=course_ids)
                timetable.courses.set(courses)

            messages.success(request, f'Timetable "{name}" created successfully!')
            return redirect('view_timetable', timetable.id)

        except Exception as e:
            messages.error(request, f'Error creating timetable: {str(e)}')
            return redirect('create_timetable')

    # GET request - show form
    departments = Department.objects.all()
    courses = Course.objects.all()
    return render(request, 'exams/create_timetable.html', {
        'departments': departments,
        'courses': courses
    })

def manual_scheduling(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    courses = Course.objects.all()
    halls = ExamHall.objects.all()
    exams = Exam.objects.filter(timetable=timetable).order_by('date', 'start_time')
    
    # Get available dates (between start_date and end_date)
    available_dates = []
    current_date = timetable.start_date
    while current_date <= timetable.end_date:
        available_dates.append(current_date)
        current_date += timedelta(days=1)
    
    # Common time slots
    time_slots = [
        ('09:00:00', '12:00:00'),
        ('14:00:00', '17:00:00')
    ]
    
    if request.method == 'POST':
        course_id = request.POST.get('course')
        date_str = request.POST.get('date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        hall_id = request.POST.get('hall')
        
        course = get_object_or_404(Course, id=course_id)
        hall = get_object_or_404(ExamHall, id=hall_id)
        exam_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Check if this course already has an exam in this timetable
        existing_exam = Exam.objects.filter(timetable=timetable, course=course).first()
        
        if existing_exam:
            # Update existing exam
            existing_exam.date = exam_date
            existing_exam.start_time = start_time
            existing_exam.end_time = end_time
            existing_exam.hall = hall
            existing_exam.save()
            messages.success(request, f'Exam for {course.code} updated successfully')
        else:
            # Create new exam
            Exam.objects.create(
                timetable=timetable,
                course=course,
                date=exam_date,
                start_time=start_time,
                end_time=end_time,
                hall=hall
            )
            messages.success(request, f'Exam for {course.code} scheduled successfully')
        
        return redirect('manual_scheduling', timetable_id=timetable.id)
    
    return render(request, 'exams/manual_scheduling.html', {
        'timetable': timetable,
        'courses': courses,
        'halls': halls,
        'exams': exams,
        'available_dates': available_dates,
        'time_slots': time_slots
    })

def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    timetable_id = exam.timetable.id
    course_code = exam.course.code
    
    exam.delete()
    
    messages.success(request, f'Exam for {course_code} has been removed from the timetable')
    return redirect('manual_scheduling', timetable_id=timetable_id)

def day_schedule(request, timetable_id, date_str):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Invalid date format")
        return redirect('view_timetable', timetable_id=timetable_id)
    
    exams = Exam.objects.filter(timetable=timetable, date=date).order_by('start_time')
    
    return render(request, 'exams/day_schedule.html', {
        'timetable': timetable,
        'date': date,
        'exams': exams
    })

def batch_scheduling(request, timetable_id):
    # Instead of rendering a template, redirect to subject pair scheduling
    messages.info(request, "Batch scheduling has been deprecated. Please use Subject Pair scheduling instead.")
    return redirect('subject_pair_scheduling', timetable_id=timetable_id)

def subject_pair_scheduling(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    subjects = Course.objects.all().select_related('department')
    classrooms = Classroom.objects.all().order_by('building', 'floor', 'name')
    departments = Department.objects.all()
    
    if request.method == 'POST':
        morning_subjects = request.POST.getlist('morning_subjects[]')
        afternoon_subjects = request.POST.getlist('afternoon_subjects[]')
        morning_dates = request.POST.getlist('morning_dates[]')
        afternoon_dates = request.POST.getlist('afternoon_dates[]')
        morning_times = request.POST.getlist('morning_times[]')
        afternoon_times = request.POST.getlist('afternoon_times[]')
        morning_rooms = request.POST.getlist('morning_rooms[]')
        afternoon_rooms = request.POST.getlist('afternoon_rooms[]')
        
        # Schedule each pair
        for i in range(len(morning_dates)):
            # Morning exam (only if subject is selected)
            if morning_subjects[i] and morning_subjects[i].strip():  # Check if subject is not empty
                try:
                    morning_subject = Course.objects.get(id=morning_subjects[i])
                    morning_date = datetime.strptime(morning_dates[i], '%Y-%m-%d').date()
                    morning_start = datetime.strptime(morning_times[i], '%H:%M').time()
                    morning_end = (datetime.combine(morning_date, morning_start) + timedelta(hours=3)).time()
                    
                    # Check if exam already exists for this subject in this timetable
                    existing_exam = Exam.objects.filter(
                        timetable=timetable,
                        course=morning_subject,
                        date=morning_date,
                        start_time=morning_start
                    ).first()
                    
                    if existing_exam:
                        # Update existing exam if room is selected
                        if morning_rooms[i] and morning_rooms[i].strip():
                            morning_room = Classroom.objects.get(id=morning_rooms[i])
                            existing_exam.hall = morning_room
                            existing_exam.save()
                    else:
                        # Only get room if one was selected
                        morning_room = None
                        if morning_rooms[i] and morning_rooms[i].strip():
                            morning_room = Classroom.objects.get(id=morning_rooms[i])
                        
                        # Create new exam
                        Exam.objects.create(
                            timetable=timetable,
                            course=morning_subject,
                            date=morning_date,
                            start_time=morning_start,
                            end_time=morning_end,
                            hall=morning_room
                        )
                except (Course.DoesNotExist, Classroom.DoesNotExist) as e:
                    messages.error(request, f'Error scheduling morning exam: {str(e)}')
                    return redirect('subject_pair_scheduling', timetable_id=timetable_id)
            
            # Afternoon exam (only if subject is selected)
            if afternoon_subjects[i] and afternoon_subjects[i].strip():  # Check if subject is not empty
                try:
                    afternoon_subject = Course.objects.get(id=afternoon_subjects[i])
                    afternoon_date = datetime.strptime(afternoon_dates[i], '%Y-%m-%d').date()
                    afternoon_start = datetime.strptime(afternoon_times[i], '%H:%M').time()
                    afternoon_end = (datetime.combine(afternoon_date, afternoon_start) + timedelta(hours=3)).time()
                    
                    # Check if exam already exists for this subject in this timetable
                    existing_exam = Exam.objects.filter(
                        timetable=timetable,
                        course=afternoon_subject,
                        date=afternoon_date,
                        start_time=afternoon_start
                    ).first()
                    
                    if existing_exam:
                        # Update existing exam if room is selected
                        if afternoon_rooms[i] and afternoon_rooms[i].strip():
                            afternoon_room = Classroom.objects.get(id=afternoon_rooms[i])
                            existing_exam.hall = afternoon_room
                            existing_exam.save()
                    else:
                        # Only get room if one was selected
                        afternoon_room = None
                        if afternoon_rooms[i] and afternoon_rooms[i].strip():
                            afternoon_room = Classroom.objects.get(id=afternoon_rooms[i])
                        
                        # Create new exam
                        Exam.objects.create(
                            timetable=timetable,
                            course=afternoon_subject,
                            date=afternoon_date,
                            start_time=afternoon_start,
                            end_time=afternoon_end,
                            hall=afternoon_room
                        )
                except (Course.DoesNotExist, Classroom.DoesNotExist) as e:
                    messages.error(request, f'Error scheduling afternoon exam: {str(e)}')
                    return redirect('subject_pair_scheduling', timetable_id=timetable_id)
        
        messages.success(request, 'Exams have been scheduled successfully')
        return redirect('view_timetable', timetable_id=timetable_id)
    
    # Get all exams for this timetable
    exams = Exam.objects.filter(timetable=timetable).order_by('date', 'start_time')
    
    # Organize exams by date
    exams_by_date = {}
    for exam in exams:
        if exam.date not in exams_by_date:
            exams_by_date[exam.date] = []
        exams_by_date[exam.date].append(exam)
    
    return render(request, 'exams/subject_pair_scheduling.html', {
        'timetable': timetable,
        'subjects': subjects,
        'departments': departments,
        'classrooms': classrooms,
        'exams_by_date': exams_by_date
    })

def subject_pair_generator(request):
    courses = Course.objects.all()
    return render(request, 'exams/subject_pair_generator.html', {
        'courses': courses
    })

def create_subject_pair_timetable(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
        first_subjects = request.POST.getlist('first_subjects[]')
        second_subjects = request.POST.getlist('second_subjects[]')
        
        # Validation
        if not name:
            messages.error(request, 'Please provide a name for the timetable')
            return redirect('subject_pair_generator')
        
        if start_date > end_date:
            messages.error(request, 'Start date cannot be after end date')
            return redirect('subject_pair_generator')
        
        if not first_subjects or not second_subjects:
            messages.error(request, 'Please select at least one subject pair')
            return redirect('subject_pair_generator')
            
        if len(first_subjects) != len(second_subjects):
            messages.error(request, 'Each first subject needs a corresponding second subject')
            return redirect('subject_pair_generator')
        
        # Create timetable
        timetable = Timetable.objects.create(
            name=name,
            start_date=start_date,
            end_date=end_date
        )
        
        current_date = start_date
        
        # Schedule each pair on consecutive days
        for i in range(len(first_subjects)):
            if current_date > end_date:
                messages.warning(request, f'Date range exceeded. Only first {i} pairs were scheduled.')
                break
                
            first_course = get_object_or_404(Course, id=first_subjects[i])
            second_course = get_object_or_404(Course, id=second_subjects[i])
            
            # Morning exam (9 AM - 12 PM)
            Exam.objects.create(
                timetable=timetable,
                course=first_course,
                date=current_date,
                start_time='09:00:00',
                end_time='12:00:00'
            )
            
            # Afternoon exam (2 PM - 5 PM)
            Exam.objects.create(
                timetable=timetable,
                course=second_course,
                date=current_date,
                start_time='14:00:00',
                end_time='17:00:00'
            )
            
            # Move to next day
            current_date += timedelta(days=1)
        
        messages.success(request, f'Timetable "{name}" has been created successfully with subject pairs')
        return redirect('subject_pair_scheduling', timetable_id=timetable.id)
        
    return redirect('subject_pair_generator')

def delete_timetable(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    
    if request.method == 'POST':
        timetable_name = timetable.name
        timetable.delete()
        messages.success(request, f'Timetable "{timetable_name}" has been deleted successfully')
        return redirect('home')
    
    return render(request, 'exams/confirm_delete_timetable.html', {
        'timetable': timetable
    })

def department_timetable(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    exams = Exam.objects.filter(timetable=timetable).select_related('course', 'hall').order_by('date', 'start_time')
    
    # Get all unique departments
    departments = set()
    for exam in exams:
        departments.add(exam.course.department)
    departments = sorted(list(departments))
    
    # Organize exams by department and then by date
    department_data = {}
    for department in departments:
        department_exams = exams.filter(course__department=department)
        
        # Organize by date
        exams_by_date = {}
        for exam in department_exams:
            date_str = exam.date.strftime('%Y-%m-%d')
            if date_str not in exams_by_date:
                exams_by_date[date_str] = []
            exams_by_date[date_str].append(exam)
        
        department_data[department] = exams_by_date
    
    return render(request, 'exams/department_timetable.html', {
        'timetable': timetable,
        'departments': departments,
        'department_data': department_data
    })

def semester_timetable(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    exams = Exam.objects.filter(timetable=timetable).select_related('course', 'hall').order_by('date', 'start_time')
    
    # Get all unique departments
    departments = set()
    for exam in exams:
        departments.add(exam.course.department)
    departments = sorted(list(departments))
    
    # Create exam grid data structure
    exam_grid = {}
    for exam in exams:
        date_str = exam.date.strftime('%Y-%m-%d')
        slot_key = f"{exam.start_time.strftime('%H:%M')} to {exam.end_time.strftime('%H:%M')}"
        
        if date_str not in exam_grid:
            exam_grid[date_str] = {}
            
        if slot_key not in exam_grid[date_str]:
            exam_grid[date_str][slot_key] = {}
            
        exam_grid[date_str][slot_key][exam.course.department] = exam
    
    # For PDF export
    if 'pdf' in request.GET:
        context = {
            'timetable': timetable,
            'departments': departments,
            'exam_grid': exam_grid,
            'now': datetime.now()
        }
        
        # Render the template
        html = render(request, 'exams/semester_timetable_pdf.html', context).content
        
        # Create PDF
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html), result)
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{timetable.name}_grid.pdf"'
            return response
        
        return HttpResponse('Error generating PDF', status=500)
    
    # For normal view (HTML)
    return render(request, 'exams/semester_timetable.html', {
        'timetable': timetable,
        'departments': departments,
        'exam_grid': exam_grid
    })

def export_grid_pdf(request, timetable_id):
    """Export the semester grid as PDF"""
    timetable = get_object_or_404(Timetable, id=timetable_id)
    exams = Exam.objects.filter(timetable=timetable).select_related('course', 'hall').order_by('date', 'start_time')
    
    # Get all unique departments
    departments = set()
    for exam in exams:
        departments.add(exam.course.department)
    departments = sorted(list(departments))
    
    # Create exam grid data structure
    exam_grid = {}
    for exam in exams:
        date_str = exam.date.strftime('%Y-%m-%d')
        slot_key = f"{exam.start_time.strftime('%H:%M')} to {exam.end_time.strftime('%H:%M')}"
        
        if date_str not in exam_grid:
            exam_grid[date_str] = {}
            
        if slot_key not in exam_grid[date_str]:
            exam_grid[date_str][slot_key] = {}
            
        exam_grid[date_str][slot_key][exam.course.department] = exam
    
    # Render the template
    context = {
        'timetable': timetable,
        'departments': departments,
        'exam_grid': exam_grid,
        'now': datetime.now()
    }
    html = render(request, 'exams/semester_timetable_pdf.html', context).content
    
    # Create PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{timetable.name}_grid.pdf"'
        return response
    
    return HttpResponse('Error generating PDF', status=500)

def manage_subjects(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            code = request.POST.get('code')
            name = request.POST.get('name')
            year = request.POST.get('year')
            department_id = request.POST.get('department')
            semester = request.POST.get('semester', 1)  # Default to 1 if not provided
            credits = request.POST.get('credits', 3)    # Default to 3 if not provided

            if not all([code, name, year, department_id]):
                messages.error(request, 'Please fill in all required fields.')
                return redirect('manage_subjects')

            try:
                department = Department.objects.get(id=department_id)
                
                # Check if subject code already exists
                if Course.objects.filter(code=code).exists():
                    messages.error(request, f'Subject code {code} already exists.')
                    return redirect('manage_subjects')

                # Create the course with the year field
                Course.objects.create(
                    code=code,
                    name=name,
                    year=year,
                    department=department,
                    semester=semester,
                    credits=credits
                )
                messages.success(request, f'Subject {code} - {name} added successfully!')
            except Department.DoesNotExist:
                messages.error(request, 'Invalid department selected.')
            except Exception as e:
                messages.error(request, f'Error adding subject: {str(e)}')

        elif action == 'edit':
            subject_id = request.POST.get('subject_id')
            code = request.POST.get('code')
            name = request.POST.get('name')
            year = request.POST.get('year')
            department_id = request.POST.get('department')
            semester = request.POST.get('semester', 1)
            credits = request.POST.get('credits', 3)

            if not all([subject_id, code, name, year, department_id]):
                messages.error(request, 'Please fill in all required fields.')
                return redirect('manage_subjects')

            try:
                subject = Course.objects.get(id=subject_id)
                department = Department.objects.get(id=department_id)
                
                # Check if subject code already exists (excluding current subject)
                if Course.objects.filter(code=code).exclude(id=subject_id).exists():
                    messages.error(request, f'Subject code {code} already exists.')
                    return redirect('manage_subjects')

                subject.code = code
                subject.name = name
                subject.year = year
                subject.department = department
                subject.semester = semester
                subject.credits = credits
                subject.save()
                
                messages.success(request, f'Subject {code} - {name} updated successfully!')
            except (Course.DoesNotExist, Department.DoesNotExist):
                messages.error(request, 'Invalid subject or department selected.')
            except Exception as e:
                messages.error(request, f'Error updating subject: {str(e)}')

        elif action == 'delete':
            subject_id = request.POST.get('subject_id')
            try:
                subject = Course.objects.get(id=subject_id)
                subject.delete()
                messages.success(request, 'Subject deleted successfully!')
            except Course.DoesNotExist:
                messages.error(request, 'Subject not found.')
            except Exception as e:
                messages.error(request, f'Error deleting subject: {str(e)}')

        return redirect('manage_subjects')

    # GET request - show form
    departments = Department.objects.all()
    courses = Course.objects.all().order_by('year', 'code')
    return render(request, 'exams/manage_subjects.html', {
        'departments': departments,
        'courses': courses
    })

def manage_classrooms(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            name = request.POST.get('name')
            capacity = request.POST.get('capacity')
            room_type = request.POST.get('room_type')
            building = request.POST.get('building')
            floor = request.POST.get('floor')
            
            try:
                Classroom.objects.create(
                    name=name,
                    capacity=capacity,
                    room_type=room_type,
                    building=building,
                    floor=floor
                )
                messages.success(request, f'Classroom {name} has been added successfully')
            except Exception as e:
                messages.error(request, f'Error adding classroom: {str(e)}')
                
        elif action == 'edit':
            room_id = request.POST.get('room_id')
            name = request.POST.get('name')
            capacity = request.POST.get('capacity')
            room_type = request.POST.get('room_type')
            building = request.POST.get('building')
            floor = request.POST.get('floor')
            
            try:
                room = Classroom.objects.get(id=room_id)
                room.name = name
                room.capacity = capacity
                room.room_type = room_type
                room.building = building
                room.floor = floor
                room.save()
                messages.success(request, f'Classroom {name} has been updated successfully')
            except Classroom.DoesNotExist:
                messages.error(request, 'Classroom not found')
            except Exception as e:
                messages.error(request, f'Error updating classroom: {str(e)}')
                
        elif action == 'delete':
            room_id = request.POST.get('room_id')
            try:
                room = Classroom.objects.get(id=room_id)
                room_name = room.name
                room.delete()
                messages.success(request, f'Classroom {room_name} has been deleted successfully')
            except Classroom.DoesNotExist:
                messages.error(request, 'Classroom not found')
            except Exception as e:
                messages.error(request, f'Error deleting classroom: {str(e)}')
    
    rooms = Classroom.objects.all()
    return render(request, 'exams/manage_classrooms.html', {'rooms': rooms})

def manage_halls(request):
    editing_hall = None  # Initialize the variable
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            name = request.POST.get('name')
            capacity = request.POST.get('capacity')
            
            if name and capacity:
                ExamHall.objects.create(
                    name=name,
                    capacity=capacity,
                    building=request.POST.get('building', 'Main Building'),
                    floor=request.POST.get('floor', 'Ground Floor'),
                    coordinates=request.POST.get('coordinates', '{"x": 0, "y": 0}')
                )
                messages.success(request, 'Exam hall added successfully.')
                return redirect('manage_halls')
                
        elif action == 'edit':
            hall_id = request.POST.get('hall_id')
            name = request.POST.get('name')
            capacity = request.POST.get('capacity')
            
            if hall_id and name and capacity:
                hall = ExamHall.objects.get(id=hall_id)
                hall.name = name
                hall.capacity = capacity
                hall.building = request.POST.get('building', 'Main Building')
                hall.floor = request.POST.get('floor', 'Ground Floor')
                hall.coordinates = request.POST.get('coordinates', '{"x": 0, "y": 0}')
                hall.save()
                messages.success(request, 'Exam hall updated successfully.')
                return redirect('manage_halls')
                
        elif action == 'delete':
            hall_id = request.POST.get('hall_id')
            
            if hall_id:
                hall = ExamHall.objects.get(id=hall_id)
                hall.delete()
                messages.success(request, 'Exam hall deleted successfully.')
                return redirect('manage_halls')
    
    # Handle edit request from GET
    edit_id = request.GET.get('edit')
    if edit_id:
        try:
            editing_hall = ExamHall.objects.get(id=edit_id)
        except ExamHall.DoesNotExist:
            messages.error(request, 'Exam hall not found.')
    
    halls = ExamHall.objects.all().order_by('name')
    context = {
        'halls': halls,
        'editing_hall': editing_hall,
    }
    return render(request, 'exams/manage_halls.html', context)

def allocate_seats(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    students = Student.objects.filter(courses=exam.course).order_by('roll_number')
    
    if request.method == 'POST':
        try:
            social_distance = int(request.POST.get('social_distance', 1))
        except (ValueError, TypeError):
            social_distance = 1  # Default to 1 if invalid input
        
        # Clear all existing seat allocations for this exam
        SeatAllocation.objects.filter(exam=exam).delete()
        
        # Get all students since we cleared the allocations
        unallocated_students = list(students)
        
        if unallocated_students:
            # Calculate classroom dimensions
            rows = int(np.sqrt(exam.hall.capacity))
            cols = exam.hall.capacity // rows
            grid = np.zeros((rows, cols), dtype=bool)
            
            # Create list to store allocations
            allocations = []
            student_index = 0
            
            try:
                if social_distance <= 1:
                    # Sequential allocation for social_distance 0 or 1
                    for row in range(rows):
                        for col in range(cols):
                            if student_index < len(unallocated_students):
                                allocations.append((row, col, unallocated_students[student_index]))
                                student_index += 1
                else:
                    # Spaced allocation for social_distance > 1
                    for row in range(rows):
                        for col in range(0, cols, social_distance):
                            if student_index < len(unallocated_students):
                                if not grid[row, col]:
                                    grid[row, col] = True
                                    allocations.append((row, col, unallocated_students[student_index]))
                                    student_index += 1
                    
                    # Fill remaining seats if needed
                    if student_index < len(unallocated_students):
                        for row in range(rows):
                            for col in range(cols):
                                if not grid[row, col] and student_index < len(unallocated_students):
                                    grid[row, col] = True
                                    allocations.append((row, col, unallocated_students[student_index]))
                                    student_index += 1
                
                # Create seat allocations in database
                for row, col, student in allocations:
                    SeatAllocation.objects.create(
                        exam=exam,
                        student=student,
                        seat_number=f"{row+1}-{col+1}",
                        row=row,
                        column=col
                    )
                
                if len(allocations) < len(unallocated_students):
                    messages.warning(request, f'Warning: Only {len(allocations)} out of {len(unallocated_students)} students could be allocated seats. Please increase the hall capacity.')
                else:
                    if social_distance <= 1:
                        messages.success(request, f'Successfully allocated seats for all {len(allocations)} students in sequential order!')
                    else:
                        messages.success(request, f'Successfully allocated seats for all {len(allocations)} students with {social_distance} seat spacing!')
                
            except Exception as e:
                messages.error(request, f'Error allocating seats: {str(e)}')
        else:
            messages.info(request, 'No students to allocate seats for.')
        
        return redirect('seat_heatmap', exam_id=exam_id)
    
    return render(request, 'exams/allocate_seats.html', {
        'exam': exam,
        'students': students,
        'hall': exam.hall
    })

def assign_invigilators(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    exams = Exam.objects.filter(timetable=timetable)
    invigilators = Invigilator.objects.all()
    departments = Department.objects.all()
    
    if request.method == 'POST':
        # Get invigilator assignments using branch and bound
        assignments = branch_and_bound_invigilator_assignment(exams, invigilators)
        
        # Apply assignments
        for exam_id, inv_ids in assignments.items():
            exam = Exam.objects.get(id=exam_id)
            exam.invigilators.set(inv_ids)
        
        messages.success(request, 'Invigilators assigned successfully!')
        return redirect('view_timetable', timetable_id)
    
    return render(request, 'exams/assign_invigilators.html', {
        'timetable': timetable,
        'exams': exams,
        'invigilators': invigilators,
        'departments': departments
    })

def add_invigilator(request, timetable_id):
    if request.method == 'POST':
        name = request.POST.get('name')
        employee_id = request.POST.get('employee_id')
        department_id = request.POST.get('department')
        max_hours = request.POST.get('max_hours', 6)
        
        try:
            department = Department.objects.get(id=department_id)
            Invigilator.objects.create(
                name=name,
                employee_id=employee_id,
                department=department,
                max_hours_per_day=max_hours
            )
            messages.success(request, f'Invigilator {name} added successfully!')
        except Exception as e:
            messages.error(request, f'Error adding invigilator: {str(e)}')
    
    return redirect('assign_invigilators', timetable_id=timetable_id)

def delete_invigilator(request, timetable_id, invigilator_id):
    if request.method == 'POST':
        try:
            invigilator = Invigilator.objects.get(id=invigilator_id)
            name = invigilator.name
            invigilator.delete()
            messages.success(request, f'Invigilator {name} deleted successfully!')
        except Invigilator.DoesNotExist:
            messages.error(request, 'Invigilator not found.')
        except Exception as e:
            messages.error(request, f'Error deleting invigilator: {str(e)}')
    
    return redirect('assign_invigilators', timetable_id=timetable_id)

def view_seat_heatmap(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    allocations = SeatAllocation.objects.filter(exam=exam)
    students = Student.objects.filter(courses=exam.course)
    
    # Calculate classroom dimensions
    if exam.hall and hasattr(exam.hall, 'capacity') and exam.hall.capacity:
        rows = int(np.sqrt(exam.hall.capacity))
        cols = exam.hall.capacity // rows
    else:
        # Default to 9x9 grid (81 seats) if hall is not available
        rows = 9
        cols = 9
    
    # Generate heatmap
    heatmap = generate_heatmap(allocations, rows, cols)
    
    if request.method == 'POST':
        roll_number = request.POST.get('roll_number')
        row = int(request.POST.get('row'))
        col = int(request.POST.get('col'))
        
        try:
            student = Student.objects.get(roll_number=roll_number)
            
            # Check if seat is already allocated
            existing_allocation = SeatAllocation.objects.filter(
                exam=exam,
                row=row,
                column=col
            ).first()
            
            if existing_allocation:
                messages.warning(request, f'Seat {row+1}-{col+1} is already allocated to {existing_allocation.student.roll_number}')
            else:
                # Create or update seat allocation
                SeatAllocation.objects.update_or_create(
                    exam=exam,
                    student=student,
                    defaults={
                        'row': row,
                        'column': col,
                        'seat_number': f"{row+1}-{col+1}"
                    }
                )
                messages.success(request, f'Seat {row+1}-{col+1} allocated to {roll_number}')
                
        except Student.DoesNotExist:
            messages.error(request, f'Student with roll number {roll_number} not found')
        except Exception as e:
            messages.error(request, f'Error allocating seat: {str(e)}')
        
        return redirect('seat_heatmap', exam_id=exam_id)
    
    return render(request, 'exams/seat_heatmap.html', {
        'exam': exam,
        'heatmap': heatmap.tolist(),
        'rows': rows,
        'cols': cols,
        'students': students,
        'allocations': allocations
    })

def mark_attendance(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    students = Student.objects.filter(courses=exam.course)
    
    if request.method == 'POST':
        for student in students:
            present = request.POST.get(f'present_{student.id}') == 'on'
            attendance, created = Attendance.objects.get_or_create(
                exam=exam,
                student=student,
                defaults={'present': present}
            )
            if not created:
                attendance.present = present
                attendance.save()
        
        messages.success(request, 'Attendance marked successfully!')
        return redirect('mark_attendance', exam_id=exam_id)
    
    return render(request, 'exams/mark_attendance.html', {
        'exam': exam,
        'students': students
    })

def select_exam(request):
    exams = Exam.objects.all().select_related('course', 'timetable').order_by('-date', 'start_time')
    return render(request, 'exams/select_exam.html', {
        'exams': exams
    })

def select_timetable(request):
    timetables = Timetable.objects.all().order_by('-created_at')
    return render(request, 'exams/select_timetable.html', {
        'timetables': timetables
    })

def add_student_to_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    
    if request.method == 'POST':
        roll_number = request.POST.get('roll_number')
        name = request.POST.get('name')
        department = request.POST.get('department')
        semester = request.POST.get('semester')
        
        try:
            # Check if student already exists
            student, created = Student.objects.get_or_create(
                roll_number=roll_number,
                defaults={
                    'name': name,
                    'department': department,
                    'semester': semester
                }
            )
            
            # If student exists but details are different, update them
            if not created:
                student.name = name
                student.department = department
                student.semester = semester
                student.save()
            
            # Add student to the course
            student.courses.add(exam.course)
            
            messages.success(request, f'Student {name} added successfully!')
        except Exception as e:
            messages.error(request, f'Error adding student: {str(e)}')
        
        return redirect('allocate_seats', exam_id=exam_id)
    
    return redirect('allocate_seats', exam_id=exam_id)

def import_students(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    
    if request.method == 'POST' and request.FILES.get('file'):
        csv_file = request.FILES['file']
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a CSV file')
            return redirect('allocate_seats', exam_id=exam_id)
        
        try:
            # Read CSV file
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            
            if not reader.fieldnames or not all(field in reader.fieldnames for field in ['Roll Number', 'Name', 'Department', 'Semester']):
                messages.error(request, 'CSV file must contain columns: Roll Number, Name, Department, Semester')
                return redirect('allocate_seats', exam_id=exam_id)
            
            students_added = 0
            for row in reader:
                try:
                    # Clean the data
                    roll_number = row['Roll Number'].strip()
                    name = row['Name'].strip()
                    department = row['Department'].strip()
                    semester = row['Semester'].strip()
                    
                    if not all([roll_number, name, department, semester]):
                        continue
                    
                    # Create or update student
                    student, created = Student.objects.get_or_create(
                        roll_number=roll_number,
                        defaults={
                            'name': name,
                            'department': department,
                            'semester': semester
                        }
                    )
                    
                    # Update existing student if needed
                    if not created:
                        student.name = name
                        student.department = department
                        student.semester = semester
                        student.save()
                    
                    # Add student to the course if not already added
                    if exam.course not in student.courses.all():
                        student.courses.add(exam.course)
                        students_added += 1
                
                except KeyError as e:
                    messages.error(request, f'Missing column in CSV: {str(e)}')
                    return redirect('allocate_seats', exam_id=exam_id)
                except Exception as e:
                    messages.error(request, f'Error importing student {roll_number}: {str(e)}')
                    continue
            
            if students_added > 0:
                messages.success(request, f'{students_added} students imported successfully!')
            else:
                messages.warning(request, 'No new students were imported. They might already be added to the exam.')
                
        except UnicodeDecodeError:
            messages.error(request, 'Please ensure the CSV file is saved with UTF-8 encoding')
        except Exception as e:
            messages.error(request, f'Error importing students: {str(e)}')
        
        return redirect('allocate_seats', exam_id=exam_id)
    
    return redirect('allocate_seats', exam_id=exam_id)

def remove_student_from_exam(request, exam_id, student_id):
    exam = get_object_or_404(Exam, id=exam_id)
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == 'POST':
        student.courses.remove(exam.course)
        messages.success(request, f'Student {student.name} removed from exam.')
    
    return redirect('allocate_seats', exam_id=exam_id)

def download_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Roll Number', 'Name', 'Department', 'Semester'])
    
    # Add sample data
    writer.writerow(['20CS001', 'John Doe', 'CSE', '4'])
    writer.writerow(['21AIDS002', 'Jane Smith', 'AIDS', '2'])
    writer.writerow(['19ECE003', 'Bob Wilson', 'ECE', '6'])
    
    return response

def manual_assign_invigilators(request, timetable_id):
    if request.method == 'POST':
        timetable = get_object_or_404(Timetable, id=timetable_id)
        exams = Exam.objects.filter(timetable=timetable)
        
        for exam in exams:
            invigilator1_id = request.POST.get(f'invigilator1_{exam.id}')
            invigilator2_id = request.POST.get(f'invigilator2_{exam.id}')
            
            # Clear current assignments
            exam.invigilators.clear()
            
            # Add new assignments if selected
            if invigilator1_id:
                exam.invigilators.add(invigilator1_id)
            if invigilator2_id:
                exam.invigilators.add(invigilator2_id)
        
        messages.success(request, 'Invigilator assignments saved successfully!')
        return redirect('assign_invigilators', timetable_id=timetable_id)
    
    return redirect('assign_invigilators', timetable_id=timetable_id)

def download_seat_heatmap(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    allocations = SeatAllocation.objects.filter(exam=exam)
    
    # Calculate classroom dimensions
    if exam.hall and hasattr(exam.hall, 'capacity') and exam.hall.capacity:
        rows = int(np.sqrt(exam.hall.capacity))
        cols = exam.hall.capacity // rows
    else:
        # Default to 9x9 grid (81 seats) if hall is not available
        rows = 9
        cols = 9
    
    # Generate heatmap
    heatmap = generate_heatmap(allocations, rows, cols)
    
    # Prepare template context
    context = {
        'exam': exam,
        'heatmap': heatmap.tolist(),
        'rows': rows,
        'cols': cols,
        'allocations': allocations,
        'is_pdf': True  # Flag to modify template rendering for PDF
    }
    
    # Render the template
    template = get_template('exams/seat_heatmap_pdf.html')
    html = template.render(context)
    
    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="seat_heatmap_{exam.id}.pdf"'
    
    # Generate PDF
    pdf = BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf_value = pdf.getvalue()
    pdf.close()
    response.write(pdf_value)
    
    return response

def download_attendance(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    students = Student.objects.filter(courses=exam.course)
    
    # Get attendance records
    attendance_records = Attendance.objects.filter(exam=exam)
    
    # Count present and absent students
    present_count = attendance_records.filter(present=True).count()
    absent_count = attendance_records.filter(present=False).count()
    
    # Prepare template context
    context = {
        'exam': exam,
        'students': students,
        'now': timezone.now(),
        'present_count': present_count,
        'absent_count': absent_count
    }
    
    # Render the template
    template = get_template('exams/attendance_pdf.html')
    html = template.render(context)
    
    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="attendance_{exam.course.code}_{exam.date}.pdf"'
    
    # Generate PDF
    pdf = BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf_value = pdf.getvalue()
    pdf.close()
    response.write(pdf_value)
    
    return response

def edit_student_allocation(request, exam_id, student_id):
    exam = get_object_or_404(Exam, id=exam_id)
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        roll_number = request.POST.get('roll_number')
        department = request.POST.get('department')
        
        # Update student details
        student.name = name
        student.roll_number = roll_number
        student.department = department
        student.save()
        
        messages.success(request, 'Student details updated successfully.')
        return redirect('allocate_seats', exam_id=exam_id)
    
    return render(request, 'exams/edit_student_allocation.html', {
        'exam': exam,
        'student': student
    })

def delete_student_allocation(request, exam_id, student_id):
    exam = get_object_or_404(Exam, id=exam_id)
    student = get_object_or_404(Student, id=student_id)
    
    try:
        allocation = SeatAllocation.objects.get(exam=exam, student_id=student_id)
        allocation.delete()
        messages.success(request, f'Seat allocation for {student.name} has been deleted successfully.')
    except SeatAllocation.DoesNotExist:
        messages.error(request, 'No seat allocation found for this student.')
    
    return redirect('allocate_seats', exam_id=exam_id)

def delete_seat_from_heatmap(request, exam_id, row, col):
    exam = get_object_or_404(Exam, id=exam_id)
    
    try:
        # Find all allocations for this seat position
        allocations = SeatAllocation.objects.filter(exam=exam, row=row, column=col)
        if allocations.exists():
            student_names = [allocation.student.name for allocation in allocations]
            allocations.delete()
            messages.success(request, f'Seat allocation(s) for {", ".join(student_names)} have been deleted successfully.')
        else:
            messages.error(request, 'No seat allocation found for this position.')
    except Exception as e:
        messages.error(request, f'Error deleting seat allocation: {str(e)}')
    
    return redirect('seat_heatmap', exam_id=exam_id)

def manage_students(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        roll_number = request.POST.get('roll_number')
        department = request.POST.get('department')
        semester = request.POST.get('semester')
        
        try:
            Student.objects.create(
                name=name,
                roll_number=roll_number,
                department=department,
                semester=semester
            )
            messages.success(request, 'Student added successfully!')
        except IntegrityError:
            messages.error(request, 'A student with this roll number already exists!')
        
        return redirect('manage_students')
    
    students = Student.objects.all().order_by('roll_number')
    return render(request, 'exams/manage_students.html', {'students': students})

def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student.delete()
    messages.success(request, 'Student deleted successfully!')
    return redirect('manage_students')

def remove_all_students_from_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    
    if request.method == 'POST':
        # Get all students in the exam
        students = Student.objects.filter(courses=exam.course)
        
        # Remove the course from all students
        for student in students:
            student.courses.remove(exam.course)
        
        messages.success(request, 'All students have been removed from the exam.')
    
    return redirect('allocate_seats', exam_id=exam_id)

def download_invigilator_assignments(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    exams = Exam.objects.filter(timetable=timetable).select_related('course', 'hall').prefetch_related('invigilators').order_by('date', 'start_time')
    
    # Prepare template context
    context = {
        'timetable': timetable,
        'exams': exams,
        'now': timezone.now()
    }
    
    # Render the template
    template = get_template('exams/invigilator_assignments_pdf.html')
    html = template.render(context)
    
    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invigilator_assignments_{timetable.name}.pdf"'
    
    # Generate PDF
    pdf = BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf_value = pdf.getvalue()
    pdf.close()
    response.write(pdf_value)
    
    return response

def edit_invigilator(request, timetable_id, invigilator_id):
    invigilator = get_object_or_404(Invigilator, id=invigilator_id)
    departments = Department.objects.all()
    
    if request.method == 'POST':
        name = request.POST.get('name')
        employee_id = request.POST.get('employee_id')
        department_id = request.POST.get('department')
        max_hours = request.POST.get('max_hours', 6)
        
        try:
            department = Department.objects.get(id=department_id)
            
            # Update invigilator details
            invigilator.name = name
            invigilator.employee_id = employee_id
            invigilator.department = department
            invigilator.max_hours_per_day = max_hours
            invigilator.save()
            
            messages.success(request, f'Invigilator {name} updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating invigilator: {str(e)}')
        
        return redirect('assign_invigilators', timetable_id=timetable_id)
    
    return render(request, 'exams/edit_invigilator.html', {
        'timetable_id': timetable_id,
        'invigilator': invigilator,
        'departments': departments
    })
