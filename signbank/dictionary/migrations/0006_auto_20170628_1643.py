# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-06-28 14:43
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0005_auto_20170601_1013'),
    ]

    operations = [
        migrations.CreateModel(
            name='SimultaneousMorphologyDefinition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(max_length=100)),
                ('morpheme', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='morpheme', to='dictionary.Morpheme')),
            ],
        ),
        migrations.AddField(
            model_name='simultaneousmorphologydefinition',
            name='parent_gloss',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parent_gloss', to='dictionary.Gloss'),
        ),
    ]
