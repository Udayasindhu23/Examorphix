from django.db import migrations, models

def set_default_values(apps, schema_editor):
    ExamHall = apps.get_model('exams', 'ExamHall')
    for hall in ExamHall.objects.all():
        hall.building = "Main Building"
        hall.floor = "Ground Floor"
        hall.coordinates = {"x": 0, "y": 0}
        hall.save()

class Migration(migrations.Migration):
    dependencies = [
        ('exams', '0006_alter_exam_hall'),
    ]

    operations = [
        migrations.AddField(
            model_name='examhall',
            name='building',
            field=models.CharField(default='Main Building', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='examhall',
            name='floor',
            field=models.CharField(default='Ground Floor', max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='examhall',
            name='coordinates',
            field=models.JSONField(default=dict),
            preserve_default=False,
        ),
        migrations.RunPython(set_default_values),
    ] 