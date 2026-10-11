import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Application',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vacancy_id', models.CharField(max_length=64)),
                ('title', models.CharField(max_length=160)),
                ('company', models.CharField(max_length=120)),
                ('score', models.PositiveSmallIntegerField(default=0)),
                ('status', models.CharField(choices=[('seleccionada', 'Seleccionada'), ('postulada', 'Postulada')], default='seleccionada', max_length=20)),
                ('cover_letter', models.TextField(blank=True, default='')),
                ('letter_source', models.CharField(blank=True, default='', max_length=20)),
                ('screening', models.JSONField(blank=True, default=list)),
                ('warnings', models.JSONField(blank=True, default=list)),
                ('audit', models.JSONField(blank=True, default=dict)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='applications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='application',
            constraint=models.UniqueConstraint(fields=('user', 'vacancy_id'), name='unique_application_per_user_vacancy'),
        ),
    ]
