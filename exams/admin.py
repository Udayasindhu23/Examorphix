from django.contrib import admin
from .models import Course, Student, ExamHall, Timetable, Exam

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'semester', 'department')
    search_fields = ('code', 'name')
    list_filter = ('semester', 'department')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('roll_number', 'name', 'semester', 'department')
    search_fields = ('roll_number', 'name')
    list_filter = ('semester', 'department')
    filter_horizontal = ('courses',)

@admin.register(ExamHall)
class ExamHallAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity', 'building', 'floor')
    search_fields = ('name', 'building')
    list_filter = ('building', 'floor')

@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'created_at')
    search_fields = ('name',)

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('course', 'date', 'start_time', 'end_time', 'hall')
    list_filter = ('date', 'hall')
    search_fields = ('course__code', 'course__name')
