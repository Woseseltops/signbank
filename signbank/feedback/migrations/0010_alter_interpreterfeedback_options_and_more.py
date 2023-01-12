# Generated by Django 4.1.4 on 2023-01-02 17:23

from django.db import migrations, models
import django.db.models.deletion
import signbank.dictionary.models


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0056_alter_dataset_options_and_more'),
        ('feedback', '0009_auto_20210602_1417'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='interpreterfeedback',
            options={'ordering': ['-date'], 'permissions': (('can_view_interpreterfeedback', 'Can View Interpreter Feedback'),)},
        ),
        migrations.AlterField(
            model_name='missingsignfeedback',
            name='direction',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'MovementDir'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='Direction', to='dictionary.fieldchoice', verbose_name='Direction'),
        ),
        migrations.AlterField(
            model_name='missingsignfeedback',
            name='handbodycontact',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'ContactType'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='HandBodyContact', to='dictionary.fieldchoice', verbose_name='HandBodyContact'),
        ),
        migrations.AlterField(
            model_name='missingsignfeedback',
            name='handform',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Handedness'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='handednessMissingSignFeedback', to='dictionary.fieldchoice', verbose_name='Handedness'),
        ),
        migrations.AlterField(
            model_name='missingsignfeedback',
            name='handinteraction',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'RelatArtic'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='HandInteraction', to='dictionary.fieldchoice', verbose_name='HandInteraction'),
        ),
        migrations.AlterField(
            model_name='missingsignfeedback',
            name='location',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Location'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='LocationMissingSignFeedback', to='dictionary.fieldchoice', verbose_name='Location'),
        ),
        migrations.AlterField(
            model_name='missingsignfeedback',
            name='movementtype',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'MovementShape'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='MovementType', to='dictionary.fieldchoice', verbose_name='MovementType'),
        ),
        migrations.AlterField(
            model_name='missingsignfeedback',
            name='relativelocation',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Location'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='Location', to='dictionary.fieldchoice', verbose_name='Location'),
        ),
        migrations.AlterField(
            model_name='missingsignfeedback',
            name='smallmovement',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'JointConfiguration'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='SmallMovement', to='dictionary.fieldchoice', verbose_name='SmallMovement'),
        ),
        migrations.AlterField(
            model_name='signfeedback',
            name='isAuslan',
            field=models.IntegerField(choices=[('0', 'N/A'), ('3', 'ASL'), ('9', 'AdaSL'), ('7', 'BISINDO'), ('10', 'Berbey SL'), ('4', 'CSL'), ('19', 'Catalan Sign Languag'), ('22', 'David Rose Signs'), ('13', 'EmblemsNL'), ('11', 'IS'), ('18', 'ISL'), ('15', 'JSL'), ('5', 'Kata Kolok'), ('23', 'Konchri Sain'), ('16', 'Korean Sign Language'), ('8', 'LSFB'), ('12', 'LaSiMa'), ('1', 'NGT'), ('6', 'NTS'), ('20', 'Sign Languages of CA'), ('14', 'TSL'), ('2', 'VGT'), ('17', 'ZEI')], verbose_name='Is this sign an Global Sign?'),
        ),
        migrations.AlterField(
            model_name='signfeedback',
            name='whereused',
            field=models.CharField(choices=[('N/A', 'N/A'), ('Groningen', 'Groningen'), ('Amsterdam', 'Amsterdam'), ('Voorburg', 'Voorburg'), ('Rotterdam', 'Rotterdam'), ('Gestel', 'Gestel'), ('Unknown', 'Unknown'), ('Beijing', 'Beijing'), ('Shanghai', 'Shanghai'), ('Nanjing', 'Nanjing'), ('Unknown', 'Unknown'), ('Ambon', 'Ambon'), ('Makassar', 'Makassar'), ('Padang', 'Padang'), ('Pontianak', 'Pontianak'), ('Singaradja', 'Singaradja'), ('Solo', 'Solo')], max_length=10, verbose_name='Where is this sign used?'),
        ),
    ]
