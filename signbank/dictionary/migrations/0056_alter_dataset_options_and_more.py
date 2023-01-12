# Generated by Django 4.1.4 on 2023-01-02 17:23

from django.db import migrations, models
import django.db.models.deletion
import signbank.dictionary.models


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0055_auto_20221123_1437'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='dataset',
            options={'permissions': (('can_view_dataset', 'View dataset'),)},
        ),
        migrations.RemoveField(
            model_name='derivationhistory',
            name='name_ar',
        ),
        migrations.RemoveField(
            model_name='derivationhistory',
            name='name_he',
        ),
        migrations.RemoveField(
            model_name='fieldchoice',
            name='name_ar',
        ),
        migrations.RemoveField(
            model_name='fieldchoice',
            name='name_he',
        ),
        migrations.RemoveField(
            model_name='handshape',
            name='name_ar',
        ),
        migrations.RemoveField(
            model_name='handshape',
            name='name_he',
        ),
        migrations.RemoveField(
            model_name='language',
            name='name_ar',
        ),
        migrations.RemoveField(
            model_name='language',
            name='name_he',
        ),
        migrations.RemoveField(
            model_name='semanticfield',
            name='name_ar',
        ),
        migrations.RemoveField(
            model_name='semanticfield',
            name='name_he',
        ),
        migrations.AlterField(
            model_name='definition',
            name='count',
            field=models.IntegerField(default=3),
        ),
        migrations.AlterField(
            model_name='definition',
            name='role',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'NoteType'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='definition', to='dictionary.fieldchoice', verbose_name='Type'),
        ),
        migrations.AlterField(
            model_name='deletedglossormedia',
            name='annotation_idgloss',
            field=models.CharField(max_length=30, verbose_name='Annotation ID Gloss'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='absOriFing',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'AbsOriFing'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='absolute_orientation_fingers', to='dictionary.fieldchoice', verbose_name='Absolute Orientation: Fingers'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='absOriPalm',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'AbsOriPalm'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='absolute_orientation_palm', to='dictionary.fieldchoice', verbose_name='Absolute Orientation: Palm'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='altern',
            field=models.BooleanField(default=False, null=True, verbose_name='Alternating Movement'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='asloantf',
            field=models.BooleanField(blank=True, null=True, verbose_name='ASL loan sign'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='asltf',
            field=models.BooleanField(blank=True, null=True, verbose_name='ASL sign'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='blendtf',
            field=models.BooleanField(blank=True, null=True, verbose_name='Blend'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='bslloantf',
            field=models.BooleanField(blank=True, null=True, verbose_name='BSL loan sign'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='bsltf',
            field=models.BooleanField(blank=True, null=True, verbose_name='BSL sign'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='comptf',
            field=models.BooleanField(blank=True, null=True, verbose_name='Compound'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='contType',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'ContactType'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contact_type', to='dictionary.fieldchoice', verbose_name='Contact Type'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='domFlex',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'DominantHandFlexion'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dominant_hand_flexion', to='dictionary.fieldchoice', verbose_name='Dominant hand - Flexion'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='domSF',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'DominantHandSelectedFingers'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dominant_hand_selected_fingers', to='dictionary.fieldchoice', verbose_name='Dominant hand - Selected Fingers'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='domhndsh_letter',
            field=models.BooleanField(blank=True, null=True, verbose_name='Strong hand letter'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='domhndsh_number',
            field=models.BooleanField(blank=True, null=True, verbose_name='Strong hand number'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='excludeFromEcv',
            field=models.BooleanField(default=False, verbose_name='Exclude from ECV'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='final_loc',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Location'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='final_primary_location', to='dictionary.fieldchoice', verbose_name='Final Primary Location'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='final_secondary_loc',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'MinorLocation'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='final_subordinate_location', to='dictionary.fieldchoice', verbose_name='Final Subordinate Location'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='handCh',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'HandshapeChange'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='handshape_change', to='dictionary.fieldchoice', verbose_name='Handshape Change'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='handedness',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Handedness'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='handedness', to='dictionary.fieldchoice', verbose_name='Handedness'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='iconType',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'iconicity'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='type_of_iconicity', to='dictionary.fieldchoice', verbose_name='Type of iconicity'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='inWeb',
            field=models.BooleanField(default=False, verbose_name='In the Web dictionary'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='initial_secondary_loc',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'MinorLocation'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='initial_subordinate_location', to='dictionary.fieldchoice', verbose_name='Initial Subordinate Location'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='isNew',
            field=models.BooleanField(default=False, null=True, verbose_name='Is this a proposed new sign?'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='locPrimLH',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Location'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='placement_active_articulator_lh', to='dictionary.fieldchoice', verbose_name='Placement Active Articulator LH'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='locprim',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Location'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='location', to='dictionary.fieldchoice', verbose_name='Location'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='locsecond',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Location'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='secondary_location', to='dictionary.fieldchoice', verbose_name='Secondary Location'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='movDir',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'MovementDir'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='movement_direction', to='dictionary.fieldchoice', verbose_name='Movement Direction'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='movMan',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'MovementMan'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='movement_manner', to='dictionary.fieldchoice', verbose_name='Movement Manner'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='movSh',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'MovementShape'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='movement_shape', to='dictionary.fieldchoice', verbose_name='Movement Shape'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='namEnt',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'NamedEntity'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='named_entity', to='dictionary.fieldchoice', verbose_name='Named Entity'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='oriCh',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'OriChange'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orientation_change', to='dictionary.fieldchoice', verbose_name='Orientation Change'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='oriChAbd',
            field=models.BooleanField(blank=True, null=True, verbose_name='Abduction change'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='oriChFlex',
            field=models.BooleanField(blank=True, null=True, verbose_name='Flexion change'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='relOriLoc',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'RelOriLoc'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='relative_orientation_location', to='dictionary.fieldchoice', verbose_name='Relative Orientation: Location'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='relOriMov',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'RelOriMov'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='relative_orientation_movement', to='dictionary.fieldchoice', verbose_name='Relative Orientation: Movement'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='relatArtic',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'RelatArtic'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='relation_between_articulators', to='dictionary.fieldchoice', verbose_name='Relation between Articulators'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='repeat',
            field=models.BooleanField(default=False, null=True, verbose_name='Repeated Movement'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='subhndsh_letter',
            field=models.BooleanField(blank=True, null=True, verbose_name='Weak hand letter'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='subhndsh_number',
            field=models.BooleanField(blank=True, null=True, verbose_name='Weak hand number'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='valence',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Valence'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='valence', to='dictionary.fieldchoice', verbose_name='Valence'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='weakdrop',
            field=models.BooleanField(blank=True, null=True, verbose_name='Weak Drop'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='weakprop',
            field=models.BooleanField(blank=True, null=True, verbose_name='Weak Prop'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='wordClass',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'WordClass'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='word_class', to='dictionary.fieldchoice', verbose_name='Word class'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='wordClass2',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'WordClass'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='word_class_2', to='dictionary.fieldchoice', verbose_name='Word class 2'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='fs2I',
            field=models.BooleanField(default=False, null=True, verbose_name='I2'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='fs2M',
            field=models.BooleanField(default=False, null=True, verbose_name='M2'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='fs2P',
            field=models.BooleanField(default=False, null=True, verbose_name='P2'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='fs2R',
            field=models.BooleanField(default=False, null=True, verbose_name='R2'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='fs2T',
            field=models.BooleanField(default=False, null=True, verbose_name='T2'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='fsI',
            field=models.BooleanField(default=False, null=True, verbose_name='I'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='fsM',
            field=models.BooleanField(default=False, null=True, verbose_name='M'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='fsP',
            field=models.BooleanField(default=False, null=True, verbose_name='P'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='fsR',
            field=models.BooleanField(default=False, null=True, verbose_name='R'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='fsT',
            field=models.BooleanField(default=False, null=True, verbose_name='T'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='hsAperture',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Aperture'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aperture', to='dictionary.fieldchoice', verbose_name='Aperture'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='hsFingConf',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'JointConfiguration'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='finger_configuration', to='dictionary.fieldchoice', verbose_name='Finger configuration'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='hsFingConf2',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'JointConfiguration'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='finger_configuration_2', to='dictionary.fieldchoice', verbose_name='Finger configuration 2'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='hsFingSel',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'FingerSelection'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='finger_selection', to='dictionary.fieldchoice', verbose_name='Finger selection'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='hsFingSel2',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'FingerSelection'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='finger_selection_2', to='dictionary.fieldchoice', verbose_name='Finger selection 2'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='hsFingUnsel',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'FingerSelection'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='unselected_fingers', to='dictionary.fieldchoice', verbose_name='Unselected fingers'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='hsNumSel',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Quantity'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quantity', to='dictionary.fieldchoice', verbose_name='Quantity'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='hsSpread',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Spreading'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='spreading', to='dictionary.fieldchoice', verbose_name='Spreading'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='hsThumb',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'Thumb'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='thumb', to='dictionary.fieldchoice', verbose_name='Thumb'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='name',
            field=models.CharField(max_length=50),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='name_en',
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='name_nl',
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='name_zh_hans',
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='ufI',
            field=models.BooleanField(default=False, null=True, verbose_name='Iu'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='ufM',
            field=models.BooleanField(default=False, null=True, verbose_name='Mu'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='ufP',
            field=models.BooleanField(default=False, null=True, verbose_name='Pu'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='ufR',
            field=models.BooleanField(default=False, null=True, verbose_name='Ru'),
        ),
        migrations.AlterField(
            model_name='handshape',
            name='ufT',
            field=models.BooleanField(default=False, null=True, verbose_name='Tu'),
        ),
        migrations.AlterField(
            model_name='morpheme',
            name='mrpType',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'MorphemeType'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='morpheme_type', to='dictionary.fieldchoice', verbose_name='Has morpheme type'),
        ),
        migrations.AlterField(
            model_name='morphologydefinition',
            name='role',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'MorphologyType'}, null=True, on_delete=django.db.models.deletion.SET_NULL, to='dictionary.fieldchoice', verbose_name='MorphologyType'),
        ),
        migrations.AlterField(
            model_name='othermedia',
            name='type',
            field=signbank.dictionary.models.FieldChoiceForeignKey(limit_choices_to={'field': 'OtherMediaType'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='other_media', to='dictionary.fieldchoice', verbose_name='Type'),
        ),
        migrations.AlterField(
            model_name='speaker',
            name='gender',
            field=models.CharField(blank=True, choices=[('m', 'Male'), ('f', 'Female'), ('o', 'Other')], max_length=1),
        ),
        migrations.AlterField(
            model_name='speaker',
            name='handedness',
            field=models.CharField(blank=True, choices=[('r', 'Right'), ('l', 'Left'), ('a', 'Ambidextrous')], max_length=1),
        ),
    ]
