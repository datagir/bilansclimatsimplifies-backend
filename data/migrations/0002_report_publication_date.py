# Generated by Django 3.2.8 on 2021-12-02 23:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='report',
            name='publication_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
