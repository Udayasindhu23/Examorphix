# Generated by Django 5.1.7 on 2025-04-08 18:56

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("exams", "0004_course_year_timetable_courses_timetable_year_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Classroom",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                (
                    "capacity",
                    models.IntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                (
                    "room_type",
                    models.CharField(
                        choices=[
                            ("classroom", "Classroom"),
                            ("laboratory", "Laboratory"),
                            ("conference", "Conference Room"),
                            ("auditorium", "Auditorium"),
                        ],
                        default="classroom",
                        max_length=20,
                    ),
                ),
                ("building", models.CharField(max_length=100)),
                ("floor", models.CharField(max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["building", "floor", "name"],
                "unique_together": {("name", "building")},
            },
        ),
    ]
