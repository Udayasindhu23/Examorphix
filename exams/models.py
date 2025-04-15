from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        ordering = ['name']

class Course(models.Model):
    YEAR_CHOICES = [
        ('1', 'First Year'),
        ('2', 'Second Year'),
        ('3', 'Third Year'),
        ('4', 'Fourth Year'),
    ]

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    year = models.CharField(max_length=1, choices=YEAR_CHOICES, default='1')
    semester = models.IntegerField(validators=[MinValueValidator(1)], default=1)
    credits = models.IntegerField(validators=[MinValueValidator(1)], default=3)

    def __str__(self):
        return f"{self.code} - {self.name} (Year {self.year})"

    class Meta:
        ordering = ['code']

class Student(models.Model):
    name = models.CharField(max_length=100)
    roll_number = models.CharField(max_length=20, unique=True)
    semester = models.IntegerField()
    department = models.CharField(max_length=100)
    courses = models.ManyToManyField(Course, related_name='students')
    hostel_block = models.CharField(max_length=50, blank=True, null=True)
    room_number = models.CharField(max_length=10, blank=True, null=True)
    
    def __str__(self):
        return f"{self.roll_number} - {self.name}"

class Invigilator(models.Model):
    name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    max_hours_per_day = models.IntegerField(default=6)
    availability = models.JSONField(default=dict)  # Stores availability for each day
    
    def __str__(self):
        return f"{self.name} ({self.employee_id})"

class ExamHall(models.Model):
    name = models.CharField(max_length=50)
    capacity = models.IntegerField()
    building = models.CharField(max_length=100)
    floor = models.CharField(max_length=50)
    coordinates = models.JSONField(default=dict)  # For internal campus map
    
    def __str__(self):
        return f"{self.name} (Capacity: {self.capacity})"

class Classroom(models.Model):
    ROOM_TYPES = [
        ('classroom', 'Classroom'),
        ('laboratory', 'Laboratory'),
        ('conference', 'Conference Room'),
        ('auditorium', 'Auditorium'),
    ]
    
    name = models.CharField(max_length=100)
    capacity = models.IntegerField(validators=[MinValueValidator(1)])
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='classroom')
    building = models.CharField(max_length=100)
    floor = models.CharField(max_length=50)
    coordinates = models.JSONField(default=dict)  # For internal campus map
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['building', 'floor', 'name']
        unique_together = ['name', 'building']
    
    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"
    
    def get_full_location(self):
        return f"{self.building} - Floor {self.floor} - {self.name}"

class Timetable(models.Model):
    YEAR_CHOICES = [
        ('1', 'First Year'),
        ('2', 'Second Year'),
        ('3', 'Third Year'),
        ('4', 'Fourth Year'),
    ]

    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    year = models.CharField(max_length=1, choices=YEAR_CHOICES, default='1')
    departments = models.ManyToManyField(Department, related_name='timetables')
    courses = models.ManyToManyField(Course, related_name='timetables')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        dept_codes = ', '.join(dept.code for dept in self.departments.all())
        return f"{self.name} - Year {self.year} ({dept_codes})"

    class Meta:
        ordering = ['-created_at']

class Exam(models.Model):
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='exams')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    hall = models.ForeignKey(Classroom, on_delete=models.SET_NULL, null=True)
    invigilators = models.ManyToManyField(Invigilator, related_name='exams')
    
    def __str__(self):
        return f"{self.course.code} - {self.date} ({self.start_time} - {self.end_time})"

class SeatAllocation(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='seat_allocations')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    seat_number = models.CharField(max_length=10)
    row = models.IntegerField()
    column = models.IntegerField()
    
    class Meta:
        unique_together = ['exam', 'student']
    
    def __str__(self):
        return f"{self.student.roll_number} - Seat {self.seat_number}"

class Attendance(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attendance')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    present = models.BooleanField(default=False)
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['exam', 'student']
    
    def __str__(self):
        return f"{self.student.roll_number} - {self.exam.course.code} - {'Present' if self.present else 'Absent'}"
