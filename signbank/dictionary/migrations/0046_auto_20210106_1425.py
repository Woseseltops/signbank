# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2021-01-06 12:50
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0044_auto_20201125_1350'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='morphologydefinition',
            name='role',
        ),
        migrations.RenameField(
            model_name='morphologydefinition',
            old_name='role_fk',
            new_name='role',
        ),
    ]
