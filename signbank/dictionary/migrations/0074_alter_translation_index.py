# Generated by Django 4.1.7 on 2023-07-13 12:40

from django.db import migrations, models


def add_default_sentencetypes(apps, schema_editor):
    """
    Add 0 and 1 choices to every FieldChoice category
    :param apps:
    :param schema_editor:
    :return:
    """
    FieldChoice = apps.get_model('dictionary', 'FieldChoice')
    new_field_choice_0, created = FieldChoice.objects.get_or_create(field='SentenceType', machine_value=0)
    new_field_choice_1, created = FieldChoice.objects.get_or_create(field='SentenceType', machine_value=1)
    new_field_choice_0.name_en = '-'
    new_field_choice_0.name_nl = '-'
    new_field_choice_0.name_zh_hans = '-'
    new_field_choice_0.name_he = '-'
    new_field_choice_0.name_ar = '-'
    new_field_choice_0.save()
    new_field_choice_1.name_en = 'N/A'
    new_field_choice_1.name_nl = 'N/A'
    new_field_choice_1.name_zh_hans = 'N/A'
    new_field_choice_1.name_he = 'N/A'
    new_field_choice_1.name_ar = 'N/A'
    new_field_choice_1.save()

class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0073_examplesentence_alter_fieldchoice_field_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='translation',
            name='index',
            field=models.IntegerField(default=1, verbose_name='Index'),
        ),
        migrations.RunPython(add_default_sentencetypes),
    ]
