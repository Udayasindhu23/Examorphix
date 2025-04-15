from django.db import migrations, models

def create_departments(apps, schema_editor):
    Department = apps.get_model('exams', 'Department')
    Course = apps.get_model('exams', 'Course')
    
    # Get unique departments from existing courses
    departments = Course.objects.values_list('department', flat=True).distinct()
    
    # Create Department objects
    department_mapping = {}
    for dept_name in departments:
        if dept_name:
            code = ''.join(word[0].upper() for word in dept_name.split())
            department = Department.objects.create(
                name=dept_name,
                code=code
            )
            department_mapping[dept_name] = department

    # Update courses with new department foreign key
    for course in Course.objects.all():
        if course.department in department_mapping:
            course.department_new = department_mapping[course.department]
            course.save()

def reverse_departments(apps, schema_editor):
    Department = apps.get_model('exams', 'Department')
    Department.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('exams', '0001_initial'),  # Make sure this matches your last migration
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('code', models.CharField(max_length=10, unique=True)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='Course',
            name='department_new',
            field=models.ForeignKey(null=True, on_delete=models.CASCADE, to='exams.department', related_name='courses'),
        ),
        migrations.RunPython(create_departments, reverse_departments),
        migrations.RemoveField(
            model_name='Course',
            name='department',
        ),
        migrations.RenameField(
            model_name='Course',
            old_name='department_new',
            new_name='department',
        ),
        migrations.AlterField(
            model_name='Course',
            name='department',
            field=models.ForeignKey(on_delete=models.CASCADE, to='exams.department', related_name='courses'),
        ),
    ] 