from colorfield.fields import ColorField
from django.db.models import Q
from django.db import models, OperationalError, ProgrammingError
from django.conf import settings
from django.http import Http404
from django.utils.encoding import escape_uri_path
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete
from django.utils.translation import gettext_noop, gettext_lazy as _, get_language
from django.utils.timezone import now
from django.forms.utils import ValidationError
from django.forms.models import model_to_dict
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.files import File
import tagging
import re
import copy
import shutil

import sys, os
import json
from collections import OrderedDict, Counter
from datetime import datetime, date

from signbank.settings.base import FIELDS, SEPARATE_ENGLISH_IDGLOSS_FIELD, LANGUAGE_CODE, DEFAULT_KEYWORDS_LANGUAGE, \
    WRITABLE_FOLDER, DATASET_METADATA_DIRECTORY, STATIC_URL, DATASET_EAF_DIRECTORY
from signbank.dictionary.translate_choice_list import choicelist_queryset_to_translated_dict

import signbank.settings
# -*- coding: utf-8 -*-

def get_default_language_id():
    language = Language.objects.get(**DEFAULT_KEYWORDS_LANGUAGE)
    if language is not None:
        return language.id
    return None


class FieldChoiceForeignKey(models.ForeignKey):
    """
    Extend ForeignKey to also hold field_choice_category
    """

    def __init__(self, *args, **kwargs):
        self.field_choice_category = "---"
        if 'field_choice_category' in kwargs:
            self.field_choice_category = kwargs.pop('field_choice_category')
        super().__init__(*args, **kwargs)


class FieldChoice(models.Model):

    # field categories
    ABSORIFING = 'AbsOriFing'
    ABSORIPALM = 'AbsOriPalm'
    APERTURE = 'Aperture'
    CONTACTTYPE = 'ContactType'
    DOMINANTHANDFLEXION = 'DominantHandFlexion'
    DOMINANTHANDSELECTEDFINGERS = 'DominantHandSelectedFingers'
    FINGERSELECTION = 'FingerSelection'
    HANDEDNESS = 'Handedness'
    HANDSHAPECHANGE = 'HandshapeChange'
    ICONICITY = 'iconicity'
    JOINTCONFIGURATION = 'JointConfiguration'
    LOCATION = 'Location'
    MINORLOCATION = 'MinorLocation'
    MORPHEMETYPE = 'MorphemeType'
    MORPHOLOGYTYPE = 'MorphologyType'
    MOVEMENTDIR = 'MovementDir'
    MOVEMENTMAN = 'MovementMan'
    MOVEMENTSHAPE = 'MovementShape'
    NAMEDENTITY = 'NamedEntity'
    NOTETYPE = 'NoteType'
    ORICHANGE = 'OriChange'
    OTHERMEDIATYPE = 'OtherMediaType'
    PATHONPATH = 'PathOnPath'
    QUANTITY = 'Quantity'
    RELORILOC = 'RelOriLoc'
    RELORIMOV = 'RelOriMov'
    RELATARTIC = 'RelatArtic'
    SPREADING = 'Spreading'
    THUMB = 'Thumb'
    VALENCE = 'Valence'
    WORDCLASS = 'WordClass'

    FIELDCHOICE_FIELDS = [
        (ABSORIFING, 'AbsOriFing'),
        (ABSORIPALM, 'AbsOriPalm'),
        (APERTURE, 'Aperture'),
        (CONTACTTYPE, 'ContactType'),
        (DOMINANTHANDFLEXION, 'DominantHandFlexion'),
        (DOMINANTHANDSELECTEDFINGERS, 'DominantHandSelectedFingers'),
        (FINGERSELECTION, 'FingerSelection'),
        (HANDEDNESS, 'Handedness'),
        (ICONICITY, 'iconicity'),
        (HANDSHAPECHANGE, 'HandshapeChange'),
        (JOINTCONFIGURATION, 'JointConfiguration'),
        (LOCATION, 'Location'),
        (MINORLOCATION, 'MinorLocation'),
        (MORPHEMETYPE, 'MorphemeType'),
        (MORPHOLOGYTYPE, 'MorphologyType'),
        (MOVEMENTDIR, 'MovementDir'),
        (MOVEMENTMAN, 'MovementMan'),
        (MOVEMENTSHAPE, 'MovementShape'),
        (NAMEDENTITY, 'NamedEntity'),
        (NOTETYPE, 'NoteType'),
        (ORICHANGE, 'OriChange'),
        (OTHERMEDIATYPE, 'OtherMediaType'),
        (PATHONPATH, 'PathOnPath'),
        (QUANTITY, 'Quantity'),
        (RELORILOC, 'RelOriLoc'),
        (RELORIMOV, 'RelOriMov'),
        (RELATARTIC, 'RelatArtic'),
        (SPREADING, 'Spreading'),
        (THUMB, 'Thumb'),
        (VALENCE, 'Valence'),
        (WORDCLASS, 'WordClass')
    ]

    field = models.CharField(max_length=50, choices=FIELDCHOICE_FIELDS)
    name = models.CharField(max_length=50)
    machine_value = models.IntegerField(
                help_text="The actual numeric value stored in the database. Created automatically.")
    field_color = ColorField(default='ffffff')

    def __str__(self):
        name = self.field + ': ' + self.name + ' (' + str(self.machine_value) + ')'
        return name

    class Meta:
        ordering = ['machine_value']


class Translation(models.Model):
    """A spoken language translation of signs"""

    gloss = models.ForeignKey("Gloss", on_delete=models.CASCADE)
    language = models.ForeignKey("Language", on_delete=models.CASCADE)
    translation = models.ForeignKey("Keyword", on_delete=models.CASCADE)
    index = models.IntegerField("Index")
    orderIndex = models.IntegerField(_("Sense Index"), default=1)

    def __str__(self):
        if self.translation and self.translation.text:
            return self.gloss.idgloss + ' (' + self.translation.text + ')'
        else:
            return self.gloss.idgloss

    def get_absolute_url(self):
        """Return a URL for a view of this translation."""

        alltrans = self.translation.translation_set.all()
        idx = 1
        for tr in alltrans:
            if tr == self:
                return "/dictionary/words/" + str(self.translation) + "-" + str(idx) + ".html"
            idx += 1
        return "/dictionary/"

    class Meta:
        unique_together = (("gloss", "language", "translation"),)
        ordering = ['gloss', 'index']

    class Admin:
        list_display = ['gloss', 'translation']
        search_fields = ['gloss__idgloss']


class Keyword(models.Model):
    """A keyword that is a possible translation equivalent of a sign"""

    def __str__(self):
        return self.text

    text = models.CharField(max_length=100, unique=True)

    def inWeb(self):
        """Return True if some gloss associated with this
        keyword is in the web version of the dictionary"""

        return len(self.translation_set.filter(gloss__inWeb__exact=True)) != 0

    class Meta:
        ordering = ['text']

    class Admin:
        search_fields = ['text']

    def match_request(self, request, n):
        """Find the translation matching a keyword request given an index 'n'
        response depends on login status
        Returns a tuple (translation, count) where count is the total number
        of matches."""

        if request.user.has_perm('dictionary.search_gloss'):
            alltrans = self.translation_set.all()
        else:
            alltrans = self.translation_set.filter(gloss__inWeb__exact=True)

        # remove crude signs for non-authenticated users if ANON_SAFE_SEARCH is on
        try:
            crudetag = tagging.models.Tag.objects.get(name='lexis:crude')
        except:
            crudetag = None

        safe = (not request.user.is_authenticated) and settings.ANON_SAFE_SEARCH
        if safe and crudetag:
            alltrans = [tr for tr in alltrans if not crudetag in tagging.models.Tag.objects.get_for_object(tr.gloss)]

        # if there are no translations, generate a 404
        if len(alltrans) == 0:
            raise Http404

        # take the nth translation if n is in range
        # otherwise take the last
        if n - 1 < len(alltrans):
            trans = alltrans[n - 1]
        else:
            trans = alltrans[len(alltrans) - 1]

        return (trans, len(alltrans))


class Definition(models.Model):
    """An English text associated with a gloss. It's called a note in the web interface"""

    def __str__(self):
        return str(self.gloss) + "/" + str(self.role)

    gloss = models.ForeignKey("Gloss", on_delete=models.CASCADE)
    text = models.TextField()
    role = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                    limit_choices_to={'field': FieldChoice.NOTETYPE},
                                    field_choice_category=FieldChoice.NOTETYPE,
                                    verbose_name=_("Note Type"), related_name="definition")
    count = models.IntegerField(default=3)
    published = models.BooleanField(default=True)

    class Meta:
        ordering = ['gloss', 'role', 'count']

    class Admin:
        list_display = ['gloss', 'role', 'count', 'text']
        list_filter = ['role']
        search_fields = ['gloss__idgloss']

    def get_role_display(self):
        return self.role.name if self.role else '-'

    def note_text(self):
        stripped_text = self.text.strip()
        if '\n' in stripped_text:
            # this function is used for displaying notes in the CSV update
            # this makes mysterious differences in old and new values visible
            stripped_text = stripped_text.replace('\n', '<br>')
        return stripped_text

    def note_tuple(self):
        return self.get_role_display(), str(self.published), str(self.count), self.note_text()


class SignLanguage(models.Model):
    """A sign language name"""

    class Meta:
        ordering = ['name']

    name = models.CharField(max_length=20)
    description = models.TextField()

    def __str__(self):
        return self.name


class Dialect(models.Model):
    """A dialect name - a regional dialect of a given Language"""

    class Meta:
        ordering = ['signlanguage', 'name']

    signlanguage = models.ForeignKey(SignLanguage, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)
    description = models.TextField()

    def __str__(self):
        return self.signlanguage.name + "/" + self.name


class SemanticField(models.Model):

    machine_value = models.IntegerField(_("Machine value"), primary_key=True)

    name = models.CharField(max_length=20, unique=True)
    field_color = ColorField(default='ffffff')
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name


class DerivationHistory(models.Model):

    machine_value = models.IntegerField(_("Machine value"), primary_key=True)

    name = models.CharField(max_length=20, unique=True)
    field_color = ColorField(default='ffffff')
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name


class RelationToForeignSign(models.Model):
    """Defines a relationship to another sign in another language (often a loan)"""

    def __str__(self):
        return str(self.gloss) + "/" + str(self.other_lang) + ',' + str(self.other_lang_gloss)

    gloss = models.ForeignKey("Gloss", on_delete=models.CASCADE)
    loan = models.BooleanField("Loan Sign", default=False)
    other_lang = models.CharField("Related Language", max_length=20)
    other_lang_gloss = models.CharField("Gloss in related language", max_length=50)

    class Meta:
        ordering = ['gloss', 'loan', 'other_lang', 'other_lang_gloss']

    class Admin:
        list_display = ['gloss', 'loan', 'other_lang', 'other_lang_gloss']
        list_filter = ['other_lang']
        search_fields = ['gloss__idgloss']


class Handshape(models.Model):
    machine_value = models.IntegerField(_("Machine value"), primary_key=True)
    name = models.CharField(max_length=50)
    field_color = ColorField(default='ffffff')
    hsNumSel = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                        limit_choices_to={'field': FieldChoice.QUANTITY},
                                        field_choice_category=FieldChoice.QUANTITY,
                                        verbose_name=_("Quantity"),
                                        related_name="quantity")

    hsFingSel = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                         limit_choices_to={'field': FieldChoice.FINGERSELECTION},
                                         field_choice_category=FieldChoice.FINGERSELECTION,
                                         verbose_name=_("Finger selection"),
                                         related_name="finger_selection")

    hsFingSel2 = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.FINGERSELECTION},
                                          field_choice_category=FieldChoice.FINGERSELECTION,
                                          verbose_name=_("Finger selection 2"),
                                          related_name="finger_selection_2")

    hsFingConf = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.JOINTCONFIGURATION},
                                          field_choice_category=FieldChoice.JOINTCONFIGURATION,
                                          verbose_name=_("Finger configuration"),
                                          related_name="finger_configuration")

    hsFingConf2 = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.JOINTCONFIGURATION},
                                          field_choice_category=FieldChoice.JOINTCONFIGURATION,
                                          verbose_name=_("Finger configuration 2"),
                                           related_name="finger_configuration_2")

    hsAperture = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.APERTURE},
                                          field_choice_category=FieldChoice.APERTURE,
                                          verbose_name=_("Aperture"),
                                          related_name="aperture")

    hsThumb = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.THUMB},
                                          field_choice_category=FieldChoice.THUMB,
                                          verbose_name=_("Thumb"),
                                       related_name="thumb")

    hsSpread = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.SPREADING},
                                          field_choice_category=FieldChoice.SPREADING,
                                          verbose_name=_("Spreading"),
                                        related_name="spreading")

    hsFingUnsel = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.FINGERSELECTION},
                                          field_choice_category=FieldChoice.FINGERSELECTION,
                                          verbose_name=_("Unselected fingers"),
                                           related_name="unselected_fingers")

    fsT = models.BooleanField(_("T"), null=True, default=False)
    fsI = models.BooleanField(_("I"), null=True, default=False)
    fsM = models.BooleanField(_("M"), null=True, default=False)
    fsR = models.BooleanField(_("R"), null=True, default=False)
    fsP = models.BooleanField(_("P"), null=True, default=False)
    fs2T = models.BooleanField(_("T2"), null=True, default=False)
    fs2I = models.BooleanField(_("I2"), null=True, default=False)
    fs2M = models.BooleanField(_("M2"), null=True, default=False)
    fs2R = models.BooleanField(_("R2"), null=True, default=False)
    fs2P = models.BooleanField(_("P2"), null=True, default=False)
    ufT = models.BooleanField(_("Tu"), null=True, default=False)
    ufI = models.BooleanField(_("Iu"), null=True, default=False)
    ufM = models.BooleanField(_("Mu"), null=True, default=False)
    ufR = models.BooleanField(_("Ru"), null=True, default=False)
    ufP = models.BooleanField(_("Pu"), null=True, default=False)

    def __str__(self):
        name = 'Handshape: ' + self.name + ' (' + str(self.machine_value) + ')'
        return name

    def field_labels(self):
        """Return the dictionary of field labels for use in a template"""
        d = dict()
        for f in self._meta.fields:
            try:
                d[f.name] = _(self._meta.get_field(f.name).verbose_name)
            except KeyError:
                d[f.name] = _(self._meta.get_field(f.name).name)
        for f in self._meta.many_to_many:
            field = self._meta.get_field(f.name)
            if hasattr(field, 'verbose_name'):
                d[f.name] = _(field.verbose_name)
            else:
                d[f.name] = _(field.name)
        return d

    def get_image_path(self, check_existance=True):
        """Returns the path within the writable and static folder"""

        foldername = str(self.machine_value) + '/'
        filename_without_extension = 'handshape_' + str(self.machine_value)

        dir_path = settings.WRITABLE_FOLDER + settings.HANDSHAPE_IMAGE_DIRECTORY + '/' + foldername

        if check_existance:
            try:
                for filename in os.listdir(dir_path):
                    if not re.match(r'.*_\d+$', filename):
                        existing_file_without_extension = os.path.splitext(filename)[0]
                        if filename_without_extension == existing_file_without_extension:
                            return settings.HANDSHAPE_IMAGE_DIRECTORY + '/' + foldername + '/' + filename
            except OSError:
                return None
        else:
            return settings.HANDSHAPE_IMAGE_DIRECTORY + '/' + foldername + '/' + filename_without_extension

    def get_fingerSelection_display(self):

        selection = ''
        if self.fsT:
            selection += 'T'
        if self.fsI:
            selection += 'I'
        if self.fsM:
            selection += 'M'
        if self.fsR:
            selection += 'R'
        if self.fsP:
            selection += 'P'
        return selection

    def set_fingerSelection_display(self):
        # set the Boolean fields corresponding to the Finger Selection pattern stored in hsFingSel
        try:
            fieldSelectionMatch = FieldChoice.objects.filter(field='FingerSelection',
                                                             machine_value=self.hsFingSel.machine_value)
        except:
            print('set_fingerSelection failed for: ', self)
            return
        if not fieldSelectionMatch:
            # no finger selection
            return
        # get the pattern, only one match is returned, in a list because of filter
        fingerSelectionPattern = fieldSelectionMatch[0].name
        self.fsT = 'T' in fingerSelectionPattern
        self.fsI = 'I' in fingerSelectionPattern
        self.fsM = 'M' in fingerSelectionPattern
        self.fsR = 'R' in fingerSelectionPattern
        self.fsP = 'P' in fingerSelectionPattern
        return

    def get_fingerSelection2_display(self):

        selection = ''
        if self.fs2T:
            selection += 'T'
        if self.fs2I:
            selection += 'I'
        if self.fs2M:
            selection += 'M'
        if self.fs2R:
            selection += 'R'
        if self.fs2P:
            selection += 'P'
        return selection

    def set_fingerSelection2_display(self):
        # set the Boolean fields corresponding to the Finger Selection pattern stored in hsFingSel2
        try:
            fieldSelectionMatch = FieldChoice.objects.filter(field='FingerSelection',
                                                             machine_value=self.hsFingSel2.machine_value)
        except:
            print('set_fingerSelection2 failed for: ', self)
            return
        if not fieldSelectionMatch:
            # no finger selection
            return
        # get the pattern, only one match is returned, in a list because of filter
        fingerSelectionPattern = fieldSelectionMatch[0].name
        self.fs2T = 'T' in fingerSelectionPattern
        self.fs2I = 'I' in fingerSelectionPattern
        self.fs2M = 'M' in fingerSelectionPattern
        self.fs2R = 'R' in fingerSelectionPattern
        self.fs2P = 'P' in fingerSelectionPattern
        return

    def get_unselectedFingers_display(self):

        selection = ''
        if self.ufT:
            selection += 'T'
        if self.ufI:
            selection += 'I'
        if self.ufM:
            selection += 'M'
        if self.ufR:
            selection += 'R'
        if self.ufP:
            selection += 'P'
        return selection

    def set_unselectedFingers_display(self):
        # set the Boolean fields corresponding to the Finger Selection pattern stored in hsFingUnsel
        try:
            fieldSelectionMatch = FieldChoice.objects.filter(field='FingerSelection',
                                                             machine_value=self.hsFingUnsel.machine_value)
        except:
            print('set_unselectedFingers failed for: ', self)
            return
        if not fieldSelectionMatch:
            # no finger selection
            return
        # get the pattern, only one match is returned, in a list because of filter
        fingerSelectionPattern = fieldSelectionMatch[0].name
        self.ufT = 'T' in fingerSelectionPattern
        self.ufI = 'I' in fingerSelectionPattern
        self.ufM = 'M' in fingerSelectionPattern
        self.ufR = 'R' in fingerSelectionPattern
        self.ufP = 'P' in fingerSelectionPattern
        return

    def count_selected_fingers(self):

        count_selected_fingers = 0
        if self.fsT:
            count_selected_fingers += 1
        if self.fsI:
            count_selected_fingers += 1
        if self.fsM:
            count_selected_fingers += 1
        if self.fsR:
            count_selected_fingers += 1
        if self.fsP:
            count_selected_fingers += 1
        return count_selected_fingers


class Gloss(models.Model):
    class Meta:
        verbose_name_plural = "Glosses"
        # ordering: for Lemma View in the Gloss List View, we need to have glosses in the same Lemma Group sorted
        ordering = ['lemma']
        permissions = (('update_video', "Can Update Video"),
                       ('search_gloss', 'Can Search/View Full Gloss Details'),
                       ('export_csv', 'Can export sign details as CSV'),
                       ('export_ecv', 'Can create an ECV export file of Signbank'),
                       ('can_publish', 'Can publish signs and definitions'),
                       ('can_delete_unpublished', 'Can delete unpub signs or defs'),
                       ('can_delete_published', 'Can delete pub signs and defs'),
                       ('view_advanced_properties', 'Include all properties in sign details'),
                       )

    def __str__(self):
        return self.idgloss

    def display_handedness(self):
        return self.handedness.name if self.handedness else self.handedness

    def display_domhndsh(self):
        return self.domhndsh.name if self.domhndsh else self.domhndsh

    def display_subhndsh(self):
        return self.subhndsh.name if self.subhndsh else self.subhndsh

    def display_locprim(self):
        return self.locprim.name if self.locprim else self.locprim

    def field_labels(self):
        """Return the dictionary of field labels for use in a template"""
        d = dict()
        for f in self._meta.fields:
            try:
                d[f.name] = _(self._meta.get_field(f.name).verbose_name)
            except KeyError:
                d[f.name] = _(self._meta.get_field(f.name).name)
        for f in self._meta.many_to_many:
            field = self._meta.get_field(f.name)
            if hasattr(field, 'verbose_name'):
                d[f.name] = _(field.verbose_name)
            else:
                d[f.name] = _(field.name)
        return d

    lemma = models.ForeignKey("LemmaIdgloss", null=True, on_delete=models.SET_NULL)

    # languages that this gloss is part of
    signlanguage = models.ManyToManyField(SignLanguage)

    # these language fields are subsumed by the language field above
    bsltf = models.BooleanField(_("BSL sign"), null=True, blank=True)
    asltf = models.BooleanField(_("ASL sign"), null=True, blank=True)

    # these fields should be reviewed - do we put them in another class too?
    aslgloss = models.CharField(_("ASL gloss"), blank=True, max_length=50)  # American Sign Language gloss
    asloantf = models.BooleanField(_("ASL loan sign"), null=True, blank=True)

    # loans from british sign language
    bslgloss = models.CharField(_("BSL gloss"), max_length=50, blank=True)
    bslloantf = models.BooleanField(_("BSL loan sign"), null=True, blank=True)

    useInstr = models.CharField(_("Annotation instructions"), max_length=50, blank=True)
    rmrks = models.CharField(_("Remarks"), max_length=50, blank=True)

    ########

    # one or more regional dialects that this gloss is used in
    dialect = models.ManyToManyField(Dialect)

    blend = models.CharField(_("Blend of"), max_length=100, null=True, blank=True)  # This field type is a guess.
    blendtf = models.BooleanField(_("Blend"), null=True, blank=True)

    compound = models.CharField(_("Compound of"), max_length=100, blank=True)  # This field type is a guess.
    comptf = models.BooleanField(_("Compound"), null=True, blank=True)

    # Phonology fields
    handedness = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.HANDEDNESS},
                                          field_choice_category=FieldChoice.HANDEDNESS,
                                          verbose_name=_("Handedness"),
                                           related_name="handedness")

    weakdrop = models.BooleanField(_("Weak Drop"), null=True, blank=True)
    weakprop = models.BooleanField(_("Weak Prop"), null=True, blank=True)

    domhndsh = models.ForeignKey(Handshape, on_delete=models.SET_NULL, null=True,
                                             verbose_name=_("Strong Hand"),
                                             related_name="strong_hand")

    subhndsh = models.ForeignKey(Handshape, on_delete=models.SET_NULL, null=True,
                                             verbose_name=_("Weak Hand"),
                                             related_name="weak_hand")

    # Support for handshape etymology
    domhndsh_number = models.BooleanField(_("Strong hand number"), null=True, blank=True)
    domhndsh_letter = models.BooleanField(_("Strong hand letter"), null=True, blank=True)
    subhndsh_number = models.BooleanField(_("Weak hand number"), null=True, blank=True)
    subhndsh_letter = models.BooleanField(_("Weak hand letter"), null=True, blank=True)

    final_domhndsh = models.ForeignKey(Handshape, on_delete=models.SET_NULL, null=True,
                                                   verbose_name=_("Final Dominant Handshape"),
                                                   related_name="final_dominant_handshape")

    final_subhndsh = models.ForeignKey(Handshape, on_delete=models.SET_NULL, null=True,
                                                   verbose_name=_("Final Subordinate Handshape"),
                                                   related_name="final_subordinate_handshape")

    locprim = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.LOCATION},
                                          field_choice_category=FieldChoice.LOCATION,
                                          verbose_name=_("Location"),
                                           related_name="location")

    final_loc = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.LOCATION},
                                          field_choice_category=FieldChoice.LOCATION,
                                          verbose_name=_("Final Primary Location"),
                                           related_name="final_primary_location")

    locVirtObj = models.CharField(_("Virtual Object"), blank=True, null=True, max_length=50)

    locsecond = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.LOCATION},
                                          field_choice_category=FieldChoice.LOCATION,
                                          verbose_name=_("Secondary Location"),
                                           related_name="secondary_location")

    initial_secondary_loc = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.MINORLOCATION},
                                          field_choice_category=FieldChoice.MINORLOCATION,
                                          verbose_name=_("Initial Subordinate Location"),
                                           related_name="initial_subordinate_location")

    final_secondary_loc = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.MINORLOCATION},
                                          field_choice_category=FieldChoice.MINORLOCATION,
                                          verbose_name=_("Final Subordinate Location"),
                                           related_name="final_subordinate_location")


    initial_palm_orientation = models.CharField(_("Initial Palm Orientation"), max_length=20, null=True, blank=True)
    final_palm_orientation = models.CharField(_("Final Palm Orientation"), max_length=20, null=True, blank=True)

    initial_relative_orientation = models.CharField(_("Initial Interacting Dominant Hand Part"), null=True,
                                                    max_length=20, blank=True)
    final_relative_orientation = models.CharField(_("Final Interacting Dominant Hand Part"), null=True, max_length=20,
                                                  blank=True)

    domSF = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.DOMINANTHANDSELECTEDFINGERS},
                                          field_choice_category=FieldChoice.DOMINANTHANDSELECTEDFINGERS,
                                          verbose_name="Dominant hand - Selected Fingers",
                                           related_name="dominant_hand_selected_fingers")

    domFlex = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.DOMINANTHANDFLEXION},
                                          field_choice_category=FieldChoice.DOMINANTHANDFLEXION,
                                          verbose_name="Dominant hand - Flexion",
                                           related_name="dominant_hand_flexion")

    oriChAbd = models.BooleanField(_("Abduction change"), null=True, blank=True)
    oriChFlex = models.BooleanField(_("Flexion change"), null=True, blank=True)

    inWeb = models.BooleanField(_("In the Web dictionary"), default=False)
    isNew = models.BooleanField(_("Is this a proposed new sign?"), null=True, default=False)
    excludeFromEcv = models.BooleanField(_("Exclude from ECV"), default=False)

    inittext = models.CharField(max_length=50, blank=True)

    morph = models.CharField(_("Morphemic Analysis"), max_length=50, blank=True)

    # zero or more morphemes that are used in this sign-word (=gloss) #175
    morphemePart = models.ManyToManyField('Morpheme', blank=True)

    sedefinetf = models.TextField(_("Signed English definition available"), null=True,
                                  blank=True)  # TODO: should be boolean
    segloss = models.CharField(_("Signed English gloss"), max_length=50, blank=True, null=True)

    sense = models.IntegerField(_("Sense Number"), null=True, blank=True,
                                help_text="If there is more than one sense of a sign enter a number here, all signs with sense>1 will use the same video as sense=1")
    sense.list_filter_sense = True

    sn = models.IntegerField(_("Sign Number"),
                             help_text="Sign Number must be a unique integer and defines the ordering of signs in the dictionary",
                             null=True, blank=True, unique=True)
    # this is a sign number - was trying
    # to be a primary key, also defines a sequence - need to keep the sequence
    # and allow gaps between numbers for inserting later signs

    StemSN = models.IntegerField(null=True, blank=True)

    relatArtic = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.RELATARTIC},
                                          field_choice_category=FieldChoice.RELATARTIC,
                                          verbose_name=_("Relation between Articulators"),
                                           related_name="relation_between_articulators")

    absOriPalm = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.ABSORIPALM},
                                          field_choice_category=FieldChoice.ABSORIPALM,
                                          verbose_name=_("Absolute Orientation: Palm"),
                                           related_name="absolute_orientation_palm")

    absOriFing = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.ABSORIFING},
                                          field_choice_category=FieldChoice.ABSORIFING,
                                          verbose_name=_("Absolute Orientation: Fingers"),
                                           related_name="absolute_orientation_fingers")

    relOriMov = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.RELORIMOV},
                                          field_choice_category=FieldChoice.RELORIMOV,
                                          verbose_name=_("Relative Orientation: Movement"),
                                           related_name="relative_orientation_movement")

    relOriLoc = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.RELORILOC},
                                          field_choice_category=FieldChoice.RELORILOC,
                                          verbose_name=_("Relative Orientation: Location"),
                                           related_name="relative_orientation_location")

    oriCh = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.ORICHANGE},
                                          field_choice_category=FieldChoice.ORICHANGE,
                                          verbose_name=_("Orientation Change"),
                                           related_name="orientation_change")

    handCh = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.HANDSHAPECHANGE},
                                          field_choice_category=FieldChoice.HANDSHAPECHANGE,
                                          verbose_name=_("Handshape Change"),
                                           related_name="handshape_change")


    repeat = models.BooleanField(_("Repeated Movement"), null=True, default=False)
    altern = models.BooleanField(_("Alternating Movement"), null=True, default=False)

    movSh = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.MOVEMENTSHAPE},
                                          field_choice_category=FieldChoice.MOVEMENTSHAPE,
                                          verbose_name=_("Movement Shape"),
                                           related_name="movement_shape")

    movDir = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.MOVEMENTDIR},
                                          field_choice_category=FieldChoice.MOVEMENTDIR,
                                          verbose_name=_("Movement Direction"),
                                           related_name="movement_direction")

    movMan = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.MOVEMENTMAN},
                                          field_choice_category=FieldChoice.MOVEMENTMAN,
                                          verbose_name=_("Movement Manner"),
                                           related_name="movement_manner")

    contType = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.CONTACTTYPE},
                                          field_choice_category=FieldChoice.CONTACTTYPE,
                                          verbose_name=_("Contact Type"),
                                           related_name="contact_type")


    phonOth = models.TextField(_("Phonology Other"), null=True, blank=True)

    mouthG = models.CharField(_("Mouth Gesture"), max_length=50, blank=True)
    mouthing = models.CharField(_("Mouthing"), max_length=50, blank=True)
    phonetVar = models.CharField(_("Phonetic Variation"), max_length=50, blank=True, )

    locPrimLH = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.LOCATION},
                                          field_choice_category=FieldChoice.LOCATION,
                                          verbose_name=_("Placement Active Articulator LH"),
                                           related_name="placement_active_articulator_lh")

    locFocSite = models.CharField(_("Placement Focal Site RH"), null=True, blank=True, max_length=5)
    locFocSiteLH = models.CharField(_("Placement Focal site LH"), null=True, blank=True, max_length=5)
    initArtOri = models.CharField(_("Orientation RH (initial)"), null=True, blank=True, max_length=5)
    finArtOri = models.CharField(_("Orientation RH (final)"), null=True, blank=True, max_length=5)
    initArtOriLH = models.CharField(_("Orientation LH (initial)"), null=True, blank=True, max_length=5)
    finArtOriLH = models.CharField(_("Orientation LH (final)"), null=True, blank=True, max_length=5)

    # Semantic fields

    iconImg = models.CharField(_("Iconic Image"), max_length=50, blank=True)

    iconType = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.ICONICITY},
                                          field_choice_category=FieldChoice.ICONICITY,
                                          verbose_name=_("Type of iconicity"),
                                           related_name="type_of_iconicity")


    namEnt = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.NAMEDENTITY},
                                          field_choice_category=FieldChoice.NAMEDENTITY,
                                          verbose_name=_("Named Entity"),
                                           related_name="named_entity")

    semField = models.ManyToManyField(SemanticField, verbose_name=_("Semantic Field"))

    wordClass = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.WORDCLASS},
                                          field_choice_category=FieldChoice.WORDCLASS,
                                          verbose_name=_("Word class"),
                                           related_name="word_class")

    wordClass2 = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.WORDCLASS},
                                          field_choice_category=FieldChoice.WORDCLASS,
                                          verbose_name=_("Word class 2"),
                                           related_name="word_class_2")

    derivHist = models.ManyToManyField(DerivationHistory, verbose_name=_("Derivation history"))

    lexCatNotes = models.CharField(_("Lexical category notes"), null=True, blank=True, max_length=300)

    valence = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                          limit_choices_to={'field': FieldChoice.VALENCE},
                                          field_choice_category=FieldChoice.VALENCE,
                                          verbose_name=_("Valence"),
                                           related_name="valence")

    concConcSet = models.CharField(_("Concepticon Concept Set"), null=True, blank=True, max_length=300)

    # Frequency fields
    tokNo = models.IntegerField(_("Number of Occurrences"), null=True, blank=True)
    tokNoSgnr = models.IntegerField(_("Number of Signers"), null=True, blank=True)

    creationDate = models.DateField(_('Creation date'), default=datetime(2015, 1, 1))
    lastUpdated = models.DateTimeField(_('Last updated'), auto_now=True)
    creator = models.ManyToManyField(User)
    alternative_id = models.CharField(max_length=50, null=True, blank=True)

    @property
    def dataset(self):
        try:
            return self.lemma.dataset
        except:
            return None

    @property
    def idgloss(self):
        try:
            return self.lemma.lemmaidglosstranslation_set.get(language=self.lemma.dataset.default_language).text
        except:
            pass
        try:
            return self.lemma.lemmaidglosstranslation_set.get(
                language__language_code_2char=settings.DEFAULT_KEYWORDS_LANGUAGE['language_code_2char']).text
        except:
            pass
        try:
            return self.lemma.lemmaidglosstranslation_set.first().text
        except:
            return str(self.id)

    def annotation_idgloss(self, language_code):
        # this function is used in Relations View to dynamically get the Annotation of related glosses
        # it is called by a template tag on the gloss using the interface language code

        interface_language_3char = dict(settings.LANGUAGES_LANGUAGE_CODE_3CHAR)[language_code]
        interface_language = Language.objects.get(language_code_3char=interface_language_3char)
        default_language = Language.objects.get(id=get_default_language_id())

        try:
            default_dataset_language = self.lemma.dataset.default_language
        except (KeyError, ObjectDoesNotExist, None):
            default_dataset_language = default_language

        try:
            return self.annotationidglosstranslation_set.get(language=interface_language).text
        except ObjectDoesNotExist:
            try:
                return self.annotationidglosstranslation_set.get(language=default_dataset_language).text
            except ObjectDoesNotExist:
                try:
                    return self.annotationidglosstranslation_set.get(language=default_language).text
                except ObjectDoesNotExist:
                    return str(self.id)

    def get_fields(self):
        return [(field.name, field.value_to_string(self)) for field in Gloss._meta.fields]

    def get_fields_dict(self):

        fields_data = []
        for field in Gloss._meta.fields:
            if field.name in settings.API_FIELDS:
                if hasattr(field, 'field_choice_category'):
                    fc_category = field.field_choice_category
                else:
                    fc_category = None
                fields_data.append((field.name, field.verbose_name.title(), fc_category))

        fields = {}
        for (f, field_verbose_name, fieldchoice_category) in fields_data:
            if fieldchoice_category:
                fieldchoice = getattr(self, f)
                if fieldchoice:
                    field_value = fieldchoice.name
                else:
                    field_value = ' '
            else:
                field_value = str(getattr(self, f))
            fields[field_verbose_name] = field_value

        # Annotation Idgloss translations
        if self.dataset:
            for language in self.dataset.translation_languages.all():
                annotationidglosstranslation = self.annotationidglosstranslation_set.filter(language=language)
                if annotationidglosstranslation and len(annotationidglosstranslation) > 0:
                    fields[_("Annotation ID Gloss") + ": %s" % language.name] = annotationidglosstranslation[0].text

        # Get all the keywords associated with this sign
        allkwds = ", ".join([x.translation.text for x in self.translation_set.all()])
        fields[Translation.__name__ + "s"] = allkwds

        # Get morphology
        fields[Morpheme.__name__ + "s"] = ", ".join([x.__str__() for x in self.simultaneous_morphology.all()])

        #
        fields["Parent glosses"] = ", ".join([x.__str__() for x in self.parent_glosses.all()])

        fields["Link"] = settings.URL + settings.PREFIX_URL + '/dictionary/gloss/' + str(self.pk)

        return fields

    def navigation(self, is_staff):
        """Return a gloss navigation structure that can be used to
        generate next/previous links from within a template page"""

        result = dict()
        result['next'] = self.next_dictionary_gloss(is_staff)
        result['prev'] = self.prev_dictionary_gloss(is_staff)
        return result

    @staticmethod
    def none_morpheme_objects():
        """Get all the GLOSS objects, but excluding the MORPHEME ones"""
        return Gloss.objects.filter(morpheme=None)

    def is_morpheme(self):
        """Test if this instance is a Morpheme or (just) a Gloss"""
        return hasattr(self, 'morpheme')

    def admin_next_gloss(self):
        """next gloss in the admin view, shortcut for next_dictionary_gloss with staff=True"""

        return self.next_dictionary_gloss(True)

    def admin_prev_gloss(self):
        """previous gloss in the admin view, shortcut for prev_dictionary_gloss with staff=True"""

        return self.prev_dictionary_gloss(True)

    def next_dictionary_gloss(self, staff=False):
        """Find the next gloss in dictionary order"""

        if staff:
            # Make sure we only include the none-Morpheme glosses
            all_glosses_ordered = Gloss.none_morpheme_objects().order_by('lemma')
        else:
            all_glosses_ordered = Gloss.objects.filter(inWeb__exact=True).order_by('lemma')

        all_glosses_ordered_pks = list(all_glosses_ordered.values_list('pk', flat=True))
        try:
            index_of_this_gloss = all_glosses_ordered_pks.index(self.pk)
        except:
            return None
        if len(all_glosses_ordered_pks) - 1 > index_of_this_gloss:
            next_gloss = all_glosses_ordered_pks[all_glosses_ordered_pks.index(self.pk) + 1]
            return Gloss.objects.get(pk=next_gloss)
        else:
            return None

    def prev_dictionary_gloss(self, staff=False):
        """DEPRICATED!!!! Find the previous gloss in dictionary order"""

        if self.sn == None:
            return None
        elif staff:
            set = Gloss.objects.filter(sn__lt=self.sn).order_by('-lemma')
        else:
            set = Gloss.objects.filter(sn__lt=self.sn, inWeb__exact=True).order_by('-lemma')
        if set:
            return set[0]
        else:
            return None

    def get_absolute_url(self):
        return "/dictionary/gloss/%s.html" % self.idgloss

    def lemma_group(self):
        glosses_with_same_lemma_group = Gloss.objects.filter(idgloss__iexact=self.idgloss).exclude(pk=self.pk)

        return glosses_with_same_lemma_group

    def data_datasets(self):
        # for use in displaying frequency for a gloss in chart format in the frequency templates
        # the frequency fields are put into a dictionary structure

        # data_datasets is a structure used in the FrequencyView template by chartjs
        # it takes the form of a list of dictionaries with predefined entries:
        #      'label' of a category and
        #      'data' for the category.
        # the data entry is a list of counts to be shown for the label category across regions
        # each dictionary in the list contains data to be shown for the regions:
        # [ { 'label' : 'Occurrences',
        #     'data' : [ < list of gloss usage occurrences per region > ]
        #   },
        #   { 'label' : 'Signers',
        #     'data' : [ < list of count of signers per regions > ]
        #    } ]

        # the total_occurrences value is used in the template to size the length of the chart axis
        # Initialise return variables
        data_datasets = []
        total_occurrences = 0

        # Prepare counters
        count_speakers_per_region = {}
        frequency_per_region = {}
        gloss_frequency_per_region = {}
        speakers_per_region = {}

        try:
            frequency_regions = self.lemma.dataset.frequency_regions()
        except (ObjectDoesNotExist, AttributeError):
            return (total_occurrences, data_datasets)

        frequency_objects = self.glossfrequency_set.all()

        # the first loop tallies up the frequency data from the gloss frequency objects
        for r in frequency_regions:
            frequency_objects_at_location = frequency_objects.filter(speaker__location=r)
            gloss_frequency_per_region[r] = frequency_objects_at_location
            count_speakers_per_region[r] = frequency_objects_at_location.count()
            frequency_per_region[r] = 0
            speakers_per_region[r] = []
            for frequency_obj_at_location in frequency_objects_at_location:
                frequency_per_region[r] += frequency_obj_at_location.frequency
                speaker = frequency_obj_at_location.speaker.identifier
                if speaker not in speakers_per_region[r]:
                    speakers_per_region[r].append(speaker)

        # the second loop puts the data in the output structure
        for c in settings.FREQUENCY_CATEGORIES:
            if c == "Occurences":
                dataset_dict = {}
                dataset_dict['label'] = c
                dataset_dict['data'] = []
                for r in frequency_regions:
                    k_value = frequency_per_region[r]
                    dataset_dict['data'].append(k_value)
                    total_occurrences += k_value
                data_datasets.append(dataset_dict)
            elif c == "Signers":
                dataset_dict = {}
                dataset_dict['label'] = c
                dataset_dict['data'] = []
                for r in frequency_regions:
                    k_value = len(speakers_per_region[r])
                    dataset_dict['data'].append(k_value)
                data_datasets.append(dataset_dict)
        return (total_occurrences, data_datasets)

    def has_frequency_data(self):

        glossfrequency_objects_count = self.glossfrequency_set.count()

        return glossfrequency_objects_count

    def speaker_data(self):

        # returns a dictionary for this gloss of all the speaker details of speakers signing this gloss
        # in the corpus to which this gloss belongs

        # two extra categories are used that are not currently displayed in the frequency table
        SEX_CATEGORIES = ['Female', 'Male', 'Other']
        AGE_CATEGORIES = ['< 25', '25 - 35', '36 - 65', '> 65', 'Unknown Age']

        # get frequency objects for this gloss
        glossfrequency_objects = self.glossfrequency_set.all()
        # collect the speakers
        speakers_with_gloss = [ gfo.speaker for gfo in glossfrequency_objects ]
        # remove duplicates
        speakers_with_gloss = list(set(speakers_with_gloss))

        # for the results, Other and Unknown Age are also tallied so that
        # the total number of speakers for the gloss is the same for gender and age
        # the interface needs this for showing percentages as well as raw data
        speaker_data = {}
        for i_key in SEX_CATEGORIES + AGE_CATEGORIES + ['Total']:
            speaker_data[i_key] = 0

        for speaker in speakers_with_gloss:
            if speaker.gender == 'm':
                speaker_data['Male'] += 1
            elif speaker.gender == 'f':
                speaker_data['Female'] += 1
            else:
                speaker_data['Other'] += 1
            speaker_age = speaker.age
            if speaker_age < 25:
                speaker_data['< 25'] += 1
            elif speaker_age <= 35:
                speaker_data['25 - 35'] += 1
            elif speaker_age <= 65:
                speaker_data['36 - 65'] += 1
            elif speaker.age > 65:
                speaker_data['> 65'] += 1
            else:
                speaker_data['Unknown Age'] += 1
            speaker_data['Total'] += 1

        return speaker_data


    def speaker_age_data(self):
        # this method returns a dictionary mapping ages
        # to number of speakers of that age that sign the gloss

        # get frequency objects for this gloss
        glossfrequency_objects = self.glossfrequency_set.all()
        # collect the speakers
        speakers_with_gloss = [ gfo.speaker for gfo in glossfrequency_objects ]
        # remove duplicates
        speakers_with_gloss = list(set(speakers_with_gloss))

        speaker_age_data = {}

        for speaker in speakers_with_gloss:
            # the resulting dictionary is going to be used in javascript so convert to string
            speaker_age = str(speaker.age)
            if speaker_age in speaker_age_data.keys():
                speaker_age_data[speaker_age] += 1
            else:
                speaker_age_data[speaker_age] = 1
        return speaker_age_data

    def homophones(self):
        """Return the set of homophones for this gloss ordered by sense number"""

        if self.sense == 1:
            relations = Relation.objects.filter(role="homophone", target__exact=self).order_by('source__sense')
            homophones = [rel.source for rel in relations]
            homophones.insert(0, self)
            return homophones
        elif self.sense > 1:
            # need to find the root and see how many senses it has
            homophones = self.relation_sources.filter(role='homophone', target__sense__exact=1)
            if len(homophones) > 0:
                root = homophones[0].target
                return root.homophones()
        return []

    def homonyms_count(self):

        homonyms_count = self.relation_sources.filter(role='homonym').count()

        return homonyms_count

    def synonyms_count(self):

        synonyms_count = self.relation_sources.filter(role='synonym').count()

        return synonyms_count

    def antonyms_count(self):

        antonyms_count = self.relation_sources.filter(role='antonym').count()

        return antonyms_count

    def hyponyms_count(self):

        hyponyms_count = self.relation_sources.filter(role='hyponym').count()

        return hyponyms_count

    def hypernyms_count(self):

        hypernyms_count = self.relation_sources.filter(role='hypernym').count()

        return hypernyms_count

    def seealso_count(self):

        seealso_count = self.relation_sources.filter(role='seealso').count()

        return seealso_count

    def paradigm_count(self):

        paradigm_count = self.relation_sources.filter(role='paradigm').count()

        return paradigm_count

    def variant_count(self):

        variant_count = self.relation_sources.filter(role='variant').count()

        return variant_count

    def relations_count(self):

        relations_count = self.relation_sources.filter(
            role__in=['homonym', 'synonyn', 'antonym', 'hyponym', 'hypernym', 'seealso', 'variant']).count()

        return relations_count

    def has_variants(self):

        variant_relations_of_sign = self.variant_relations()

        variant_relation_objects = [x.target for x in variant_relations_of_sign]

        return variant_relation_objects

    def pattern_variants(self):

        # this function is used in Frequencies
        # the self object is included in the results

        # Build query
        # the stems are language, text pairs
        # the variant patterns to be searched for have alternative "-<letter> or "-<number>" patterns.
        this_sign_stems = self.get_stems()

        this_sign_dataset = self.lemma.dataset
        this_sign_language = self.lemma.dataset.default_language
        queries = []
        for this_sign_stem in this_sign_stems:
            this_matches = r'^' + re.escape(this_sign_stem[1]) + r'$'
            queries.append(Q(annotationidglosstranslation__text__regex=this_matches, annotationidglosstranslation__language=this_sign_language,
                             lemma__dataset=this_sign_dataset))
            this_also_matches = r'^' + re.escape(this_sign_stem[1]) + r'\-[A-Z]$'
            queries.append(Q(annotationidglosstranslation__text__regex=this_also_matches, annotationidglosstranslation__language=this_sign_language,
                             lemma__dataset=this_sign_dataset))
            this_even_matches = r'^' + re.escape(this_sign_stem[1]) + r'\-[1-9]$'
            queries.append(Q(annotationidglosstranslation__text__regex=this_even_matches, annotationidglosstranslation__language=this_sign_language,
                             lemma__dataset=this_sign_dataset))

        merged_query_expression = Q()
        if queries:
            # queries list is non-empty
            # remove one Q expression and put it in merged_query_expression
            merged_query_expression = queries.pop()
            for q in queries:
                # iterate  over the remaining Q expressings or-ing them with the rest
                merged_query_expression |= q

        if merged_query_expression:
            # exclude glosses that have a relation to this gloss
            related_gloss_ids = [relation.target.id for relation in self.other_relations()]
            pattern_variants = Gloss.objects.filter(merged_query_expression).exclude(id__in=related_gloss_ids).distinct()
        else:
            pattern_variants = [ self ]
        return pattern_variants

    def other_relations(self):

        other_relations = self.relation_sources.filter(
            role__in=['homonym', 'synonyn', 'antonym', 'hyponym', 'hypernym', 'seealso'])

        return other_relations

    def variant_relations(self):

        variant_relations = self.relation_sources.filter(role__in=['variant'])

        return variant_relations

    # this function is used by Homonyms List view
    # a boolean is paired with saved homonym relation targets to tag duplicates
    def homonym_relations(self):

        homonym_relations = self.relation_sources.filter(role__in=['homonym'])

        homonyms = [x.target for x in homonym_relations]

        tagged_homonym_objects = []
        seen = []
        for o in homonyms:
            if o.id in seen:
                tagged_homonym_objects.append((o, True))
                seen.append(o.id)
            else:
                tagged_homonym_objects.append((o, False))
                seen.append(o.id)

        return tagged_homonym_objects

    def get_stems(self):
        if not self.lemma or not self.lemma.dataset:
            return []
        annotations = self.annotationidglosstranslation_set.all()
        if not annotations:
            return []
        this_sign_language = self.lemma.dataset.default_language
        stems = []
        for annotation in annotations:
            if not annotation.language == this_sign_language:
                continue
            this_text = annotation.text
            if len(this_text) < 2:
                # not long enough to include suffix
                continue
            suffix_text = this_text[-2]
            if suffix_text == '-':
                # this matches the pattern
                stem_text = this_text[:-2]
                stems.append((this_sign_language, stem_text))
        return stems

    def gloss_relations(self):

        variant_relations = self.relation_sources.filter(role__in=['variant'])

        other_relations = self.relation_sources.filter(role__in=['homonym', 'synonyn', 'antonym',
                                                                 'hyponym', 'hypernym', 'seealso', 'paradigm'])

        return (other_relations, variant_relations)


    def phonology_matrix_homonymns(self, use_machine_value=False):
        # this method uses string representations for Boolean values
        # in order to distinguish between null values, False values, and Neutral values

        phonology_dict = dict()
        for field in FIELDS['phonology']:
            gloss_field = Gloss._meta.get_field(field)
            if isinstance(gloss_field, models.CharField) or isinstance(gloss_field, models.TextField):
                continue
            field_value = getattr(self, gloss_field.name)
            if isinstance(field_value, Handshape):
                if field_value is None:
                    # this differentiates between null field choice fields (here) versus null Boolean fields
                    # which get mapped to either 'False' or 'Neutral'
                    phonology_dict[field] = None
                else:
                    phonology_dict[field] = str(field_value.machine_value)
            elif hasattr(gloss_field, 'field_choice_category'):
                if field_value is None:
                    # this differentiates between null field choice fields (here) versus null Boolean fields
                    # which get mapped to either 'False' or 'Neutral'
                    phonology_dict[field] = None
                else:
                    phonology_dict[field] = str(field_value.machine_value if use_machine_value else field_value.id)
            else:
                # gloss_field is a Boolean
                # TO DO: check these conversions to Strings instead of Booleans

                if field_value is not None:
                    if field_value:
                        # machine value is 1
                        phonology_dict[field] = 'True'
                    else:
                        # machine value is 0
                        phonology_dict[field] = 'False'
                else:
                    # machine value is None, for weakdrop and weakprop, this is Neutral
                    # value is Neutral
                    if field in settings.HANDEDNESS_ARTICULATION_FIELDS:
                        phonology_dict[field] = 'Neutral'
                    else:
                        phonology_dict[field] = 'False'

        return phonology_dict

    def minimal_pairs_tuple(self):
        minimal_pairs_fields = settings.MINIMAL_PAIRS_FIELDS

        values_list = []
        for f in minimal_pairs_fields:
            field_value = getattr(self, f)
            if isinstance(field_value, Handshape):
                if field_value and field_value.machine_value not in ['0', '1']:
                    values_list.append(str(field_value.machine_value))
                else:
                    # if the field choice value is None or '-' or 'N/A' use None for computing minimal pairs
                    values_list.append(None)
            elif isinstance(field_value, FieldChoice):
                if field_value and field_value.machine_value not in ['0', '1']:
                    values_list.append(str(field_value.id))
                else:
                    # if the field choice value is None or '-' or 'N/A' use None for computing minimal pairs
                    values_list.append(None)
            else:
                values_list.append(field_value)
        values_tuple = tuple(values_list)

        return values_tuple

    def minimalpairs_objects(self):
        minimalpairs_objects_list = []

        if not self.lemma or not self.lemma.dataset:
            # take care of glosses without a dataset
            return minimalpairs_objects_list

        focus_gloss_values_tuple = self.minimal_pairs_tuple()
        index_of_handedness = settings.MINIMAL_PAIRS_FIELDS.index('handedness')
        handedness_of_this_gloss = focus_gloss_values_tuple[index_of_handedness]

        # Ignore minimal pairs when the Handedness of this gloss is X, if it's a possible field choice
        try:
            handedness_X = str(FieldChoice.objects.get(field='Handedness', name__exact='X').id)

        except ObjectDoesNotExist:
            # print('minimalpairs_objects: Handedness X is not defined')
            handedness_X = ''

        empty_handedness = [ str(fc.id) for fc in FieldChoice.objects.filter(field='Handedness', name__in=['-','N/A']) ]

        if (handedness_of_this_gloss in empty_handedness or handedness_of_this_gloss == handedness_X):
            # ignore gloss with empty or X handedness
            return minimalpairs_objects_list

        # the next few lines to determine the initial minimal_pairs_fields_qs look long-winded
        finger_spelling_glosses = [a_idgloss_trans.gloss_id for a_idgloss_trans in
                                   AnnotationIdglossTranslation.objects.filter(text__startswith="#")]
        q = Q(lemma__dataset_id=self.lemma.dataset.id)

        q_number_or_letter = Q(**{'domhndsh_number': True}) | Q(**{'subhndsh_number': True}) | \
                             Q(**{'domhndsh_letter': True}) | Q(**{'subhndsh_letter': True})

        # exclude glosses with empty handedness or empty strong hand
        handedness_filter = 'handedness__name__in'
        handedness_null = 'handedness__isnull'
        strong_hand_filter = 'domhndsh__name__in'
        strong_hand_null = 'domhndsh__isnull'
        empty_value = ['-','N/A']

        q_empty = Q(**{handedness_null: True}) | \
                  Q(**{strong_hand_null: True}) | \
                  Q(**{handedness_filter: empty_value}) | \
                  Q(**{strong_hand_filter: empty_value})

        minimal_pairs_fields_qs = Gloss.objects.select_related('lemma').exclude(
                id__in=finger_spelling_glosses).exclude(id=self.id).filter(q).exclude(q_empty).exclude(q_number_or_letter)

        minimal_pairs_fields = settings.MINIMAL_PAIRS_FIELDS

        from django.db.models import When, Case, BooleanField, IntegerField

        zipped_tuples = zip(minimal_pairs_fields, focus_gloss_values_tuple)

        for (field, value_of_this_field) in zipped_tuples:
            gloss_field = Gloss._meta.get_field(field)
            if isinstance(gloss_field, Handshape):
                # field is a handshape
                different_field = 'different_' + field
                field_compare = field + '__exact'
                different_case = Case(When(**{ field_compare : value_of_this_field , 'then' : 0 }), default=1, output_field=IntegerField())
                minimal_pairs_fields_qs = minimal_pairs_fields_qs.annotate(**{ different_field : different_case })
            elif hasattr(gloss_field, 'field_choice_category'):
                # field is a choice list
                different_field = 'different_' + field
                field_compare = field + '__exact'
                different_case = Case(When(**{ field_compare : value_of_this_field , 'then' : 0 }), default=1, output_field=IntegerField())
                minimal_pairs_fields_qs = minimal_pairs_fields_qs.annotate(**{ different_field : different_case })

            else:
                # field is a Boolean
                different_field = 'different_' + field
                field_compare = field + '__exact'
                if value_of_this_field == True:
                    different_case = Case(When(**{ field_compare : True , 'then' : 0 }), default=1, output_field=IntegerField())

                    minimal_pairs_fields_qs = minimal_pairs_fields_qs.annotate(**{ different_field : different_case })

                else:
                    # Boolean values might be empty, so compare to True and invert
                    different_case = Case(When(**{ field_compare : True , 'then': 1 }), default=0, output_field=IntegerField())

                    minimal_pairs_fields_qs = minimal_pairs_fields_qs.annotate(**{ different_field : different_case })

        # construct extra filter to check that the number of different fields is exactly 1
        extra_comparison = ' + '.join('different_'+field for field in minimal_pairs_fields)
        extra_comparison = '(' + extra_comparison + ') = 1'
        extra_comparison = [ extra_comparison ]

        minimal_pairs_fields_qs = minimal_pairs_fields_qs.extra(where= extra_comparison )

        for o in minimal_pairs_fields_qs:
            # return only the minimal pairs glosses, without the annotations
            # since these were previously reduced to values for computation, fetch the objects
            next_gloss = Gloss.objects.get(pk=o.__dict__['id'])
            minimalpairs_objects_list.append(next_gloss)

        return minimalpairs_objects_list


    def minimal_pairs_dict(self):

        focus_gloss_values_tuple = self.minimal_pairs_tuple()

        index_of_handedness = settings.MINIMAL_PAIRS_FIELDS.index('handedness')
        handedness_of_this_gloss = focus_gloss_values_tuple[index_of_handedness]

        minimal_pairs_fields = dict()

        empty_handedness = [str(fc.id) for fc in
                            FieldChoice.objects.filter(field='Handedness', name__in=['-', 'N/A'])]

        # If handedness is not defined for this gloss, don't bother to look up minimal pairs
        if handedness_of_this_gloss in empty_handedness:
            return minimal_pairs_fields

        # Restrict minimal pairs search if gloss has empty phonology field for Strong Hand
        index_of_handshape = settings.MINIMAL_PAIRS_FIELDS.index('domhndsh')
        handshape_of_this_gloss = focus_gloss_values_tuple[index_of_handshape]
        empty_handshape = [str(fc.machine_value) for fc in
                            Handshape.objects.filter(name__in=['-', 'N/A'])]

        if handshape_of_this_gloss in empty_handshape:
            return minimal_pairs_fields

        mpos = self.minimalpairs_objects()

        for o in mpos:
            other_gloss_values_tuple = o.minimal_pairs_tuple()
            zipped_tuples = zip(settings.MINIMAL_PAIRS_FIELDS, focus_gloss_values_tuple, other_gloss_values_tuple)

            for (field_name, field_value, other_field_value) in zipped_tuples:
                if field_value in [None, '0'] and other_field_value in [None,'0']:
                    continue
                if field_value != other_field_value:
                    gloss_field = Gloss._meta.get_field(field_name)
                    field_label = gettext_noop(gloss_field.verbose_name)
                    if field_name in ['domhndsh', 'subhndsh', 'final_domhndsh', 'final_subhndsh']:
                        if field_value is not None:
                            field_value = Handshape.objects.get(machine_value=int(field_value)).name
                        if other_field_value is not None:
                            other_field_value = Handshape.objects.get(machine_value=int(other_field_value)).name
                    if hasattr(gloss_field, 'field_choice_category'):
                        if field_value is not None:
                            field_value = FieldChoice.objects.get(id=int(field_value)).name
                        if other_field_value is not None:
                            other_field_value = FieldChoice.objects.get(id=int(other_field_value)).name
                    minimal_pairs_fields[o] = {field_name: (field_label, field_name, field_value, other_field_value, fieldname_to_kind(field_name))}

        return minimal_pairs_fields

    # Homonyms
    # these are now defined in settings

    def homonym_objects(self):

        homonym_objects_list = []

        if not self.lemma or not self.lemma.dataset:
            # take care of glosses without a dataset
            return homonym_objects_list

        phonology_for_gloss = self.phonology_matrix_homonymns()
        handedness_of_this_gloss = phonology_for_gloss['handedness']

        homonym_objects_list = []

        # Ignore homonyms when the Handedness of this gloss is X, if it's a possible field choice
        try:
            handedness_X = str(FieldChoice.objects.get(field='Handedness', name__exact='X').id)

        except ObjectDoesNotExist:
            # print('homonym_objects: Handedness X is not defined')
            handedness_X = ''

        empty_handedness = [ str(fc.id) for fc in FieldChoice.objects.filter(field='Handedness', name__in=['-','N/A']) ]

        if (handedness_of_this_gloss in empty_handedness or handedness_of_this_gloss == handedness_X):
            # ignore gloss with empty or X handedness
            return homonym_objects_list

        q = Q(lemma__dataset_id=self.lemma.dataset.id)

        foreign_key_fields = [f.name for f in Gloss._meta.fields if isinstance(f, FieldChoiceForeignKey)]
        minimal_pair_fields = []
        for field in settings.MINIMAL_PAIRS_FIELDS:
            minimal_pair_fields.append(field)

        for field in minimal_pair_fields + settings.HANDSHAPE_ETYMOLOGY_FIELDS + settings.HANDEDNESS_ARTICULATION_FIELDS:
            value_of_this_field = phonology_for_gloss.get(field)

            if value_of_this_field is None and field in foreign_key_fields:
                # catch not set FK fields
                comparison = field + '__isnull'
                q.add(Q(**{comparison: True}), q.AND)
            elif value_of_this_field == 'False' and field in settings.HANDEDNESS_ARTICULATION_FIELDS:
                # fields weakdrop and weakprop use 3-valued logic, False only matches False, not Null
                comparison1 = field + '__exact'
                q.add(Q(**{comparison1: False}), q.AND)
            elif value_of_this_field in ['-',' ','','None','False', None]:
                # field is repeat or altern
                comparison1 = field + '__isnull'
                comparison2 = field + '__exact'
                comparison3 = field + '__exact'
                q_or = Q(**{comparison1: True})
                q_or |= Q(**{comparison2: '0'})
                q_or |= Q(**{comparison3: False})
                q.add(q_or, q.AND)
            elif (value_of_this_field == 'Neutral'):
                # Can only match Null, not True or False
                comparison = field + '__isnull'
                q.add(Q(**{comparison: True}), q.AND)
            elif (value_of_this_field == 'True'):
                comparison = field + '__exact'
                q.add(Q(**{comparison: True}), q.AND)
            else:
                # FK fields are str(int) and fall through to here
                comparison = field + '__exact'
                if field in foreign_key_fields:
                    # look up based on field choice id
                    value_of_this_field = int(value_of_this_field)
                    comparison = field + '_id__exact'
                q.add(Q(**{comparison: value_of_this_field}), q.AND)

        qs = Gloss.objects.select_related('lemma').exclude(id=self.id).filter(q)

        for o in qs:
            homonym_objects_list.append(o)
        #
        return homonym_objects_list
        # return qs

    def homonyms(self):
        #  this function returns a 3-tuple of information about homonymns for this gloss

        homonyms_of_this_gloss = []

        if not self.lemma or not self.lemma.dataset:
            # take care of glosses without a dataset
            return ([], [], [])

        gloss_homonym_relations = self.relation_sources.filter(role='homonym')

        list_of_homonym_relations = [r for r in gloss_homonym_relations]

        targets_of_homonyms_of_this_gloss = [r.target for r in gloss_homonym_relations]

        paren = ')'

        phonology_for_gloss = self.phonology_matrix_homonymns()

        handedness_of_this_gloss = phonology_for_gloss['handedness']

        # Ignore homonyms when the Handedness of this gloss is X, if it's a possible field choice
        try:
            handedness_X = str(FieldChoice.objects.get(field='Handedness', name__exact='X').id)

        except ObjectDoesNotExist:
            print('homonyms: Handedness X is not defined')
            return ([], [], [])

        empty_handedness = [ str(fc.id) for fc in FieldChoice.objects.filter(field='Handedness', name__in=['-','N/A']) ]

        if handedness_of_this_gloss in empty_handedness or handedness_of_this_gloss == handedness_X:
            # ignore gloss with empty or X handedness
            return ([], [], [])

        handshape_of_this_gloss = phonology_for_gloss['domhndsh']

        empty_handshape = [str(fc.machine_value) for fc in
                            Handshape.objects.filter(name__in=['-', 'N/A'])]

        if handshape_of_this_gloss in empty_handshape:
            return ([], [], [])

        homonyms_of_this_gloss = [g for g in self.homonym_objects()]

        homonyms_not_saved = []
        saved_but_not_homonyms = []

        for r in list_of_homonym_relations:
            if (not r.target in homonyms_of_this_gloss):
                saved_but_not_homonyms += [r.target]
        for h in homonyms_of_this_gloss:
            if (not h in targets_of_homonyms_of_this_gloss):
                homonyms_not_saved += [h]

        return (homonyms_of_this_gloss, homonyms_not_saved, saved_but_not_homonyms)

    def get_image_path(self, check_existance=True):
        """Returns the path within the writable and static folder"""
        glossvideo = self.glossvideo_set.filter(version=0)
        if glossvideo:
            glossvideo = glossvideo[0]
            videofile_path = str(glossvideo.videofile)
            videofile_path_without_extension, extension = os.path.splitext(videofile_path)

            if check_existance:
                for extension in settings.SUPPORTED_CITATION_IMAGE_EXTENSIONS:
                    imagefile_path = videofile_path_without_extension.replace("glossvideo", "glossimage") + extension
                    try:
                        imagefile_path_exists = os.path.exists(os.path.join(settings.WRITABLE_FOLDER, imagefile_path))
                    except:
                        imagefile_path_exists = False
                    if check_existance and imagefile_path_exists:
                        return imagefile_path
        else:
            # If there is no GlossVideo, see whether there is an image on disk anyway
            # TODO Create a more elegant solution, e.g. by introducing a GlossImage model

            # Create a dummy GlossVideo
            from signbank.video.models import GlossVideo, get_video_file_path
            glossvideo = GlossVideo(gloss=self)
            videofile_path = get_video_file_path(glossvideo, 'does-not-exist.mp4')

            videofile_path_without_extension, extension = os.path.splitext(videofile_path)

            for extension in settings.SUPPORTED_CITATION_IMAGE_EXTENSIONS:
                imagefile_path = videofile_path_without_extension.replace("glossvideo", "glossimage") + extension
                try:
                    imagefile_path_exists = os.path.exists(os.path.join(settings.WRITABLE_FOLDER, imagefile_path))
                except:
                    imagefile_path_exists = False
                if check_existance and imagefile_path_exists:
                    return imagefile_path
        return ''

    def get_image_url(self):
        return escape_uri_path(self.get_image_path())

    def get_video_path(self):
        try:
            glossvideo = self.glossvideo_set.get(version=0)
            return str(glossvideo.videofile)
        except ObjectDoesNotExist:
            return ''
        except MultipleObjectsReturned:
            # Just return the first
            glossvideos = self.glossvideo_set.filter(version=0)
            return str(glossvideos[0].videofile)

    def get_video_path_prefix(self):
        try:
            glossvideo = self.glossvideo_set.get(version=0)
            prefix, extension = os.path.splitext(str(glossvideo))
            return prefix
        except ObjectDoesNotExist:
            return ''

    def get_video(self):
        """Return the video object for this gloss or None if no video available"""

        video_path = self.get_video_path()
        filepath = os.path.join(settings.WRITABLE_FOLDER, video_path)
        if os.path.exists(filepath.encode('utf-8')):
            return video_path
        else:
            return ''

    def count_videos(self):
        """Return a count of the number of videos as indicated in the database"""

        return self.glossvideo_set.count()

    def get_video_url(self):
        """return  the url of the video for this gloss which may be that of a homophone"""
        video_url_or_empty_string = escape_uri_path(self.get_video())

        return video_url_or_empty_string

    def has_video(self):
        """Test to see if the video for this sign is present"""

        return self.get_video() not in ['', None]

    def add_video(self, user, videofile, recorded):
        # Preventing circular import
        from signbank.video.models import GlossVideo, GlossVideoHistory, get_video_file_path

        # Backup the existing video objects stored in the database
        existing_videos = GlossVideo.objects.filter(gloss=self)
        for video_object in existing_videos:
            video_object.reversion(revert=False)

        # Create a new GlossVideo object
        if isinstance(videofile, File):
            video = GlossVideo(gloss=self)
            video.videofile.save(get_video_file_path(video, str(videofile)), videofile)
        else:
            video = GlossVideo(videofile=videofile, gloss=self)
        video.save()
        video.ch_own_mod_video()
        video.make_small_video()
        video.make_poster_image()

        # Create a GlossVideoHistory object
        video_file_full_path = os.path.join(WRITABLE_FOLDER, str(video.videofile))
        glossvideohistory = GlossVideoHistory(action="upload", gloss=self, actor=user,
                                              uploadfile=videofile, goal_location=video_file_full_path)
        glossvideohistory.save()

        return video

    def create_citation_image(self):
        from signbank.video.models import GlossVideo
        glossvideo = GlossVideo.objects.get(gloss=self, version=0)
        glossvideo.make_poster_image()

    def published_definitions(self):
        """Return a query set of just the published definitions for this gloss
        also filter out those fields not in DEFINITION_FIELDS"""

        defs = self.definition_set.filter(published__exact=True)

        return [d for d in defs if d.role in settings.DEFINITION_FIELDS]

    def definitions(self):
        """gather together the definitions for this gloss"""

        defs = dict()
        for d in self.definition_set.all().order_by('count'):
            if not d.role in defs:
                defs[d.role] = []

            defs[d.role].append(d.text)
        return defs

    def options_to_json(self, options):
        """Convert an options list to a json dict"""

        result = []
        for k, v in options:
            result.append('"%s":"%s"' % (k, v))
        return "{" + ",".join(result) + "}"

    def definition_role_choices_json(self):
        """Return JSON for the definition role choice list"""
        definition_role_choices = choicelist_queryset_to_translated_dict(
                                 FieldChoice.objects.filter(field='NoteType'),
                                 ordered=False, id_prefix=''
                             )
        return self.options_to_json(definition_role_choices)

    def relation_role_choices_json(self):
        """Return JSON for the relation role choice list"""

        return self.options_to_json(RELATION_ROLE_CHOICES)

    def handedness_weak_choices_json(self):
        """Return JSON for the etymology choice list"""
        from signbank.dictionary.forms import NEUTRALBOOLEANCHOICES

        return self.options_to_json(NEUTRALBOOLEANCHOICES)

    def handedness_weak_drop_prop_json(self):
        """Return JSON for the etymology choice list"""

        NEUTRALBOOLEANCHOICES = [('None', _('Neutral')), ('True', _('Yes')), ('False', _('No'))]

        return self.options_to_json(NEUTRALBOOLEANCHOICES)

    def handedness_weak_drop_reverse_prop_json(self):
        """Return JSON for the etymology choice list"""

        NEUTRALBOOLEANCHOICES = [('1', _('Neutral')), ('2', _('Yes')), ('3', _('No'))]

        return self.options_to_json(NEUTRALBOOLEANCHOICES)

    def handedness_weak_drop_json(self):
        """Return JSON for the etymology choice list"""

        NEUTRALBOOLEANCHOICES = [(_('Neutral'), '1'), (_('Yes'), '2'), (_('No'), '3')]

        return self.options_to_json(NEUTRALBOOLEANCHOICES)

    @staticmethod
    def variant_role_choices():

        return '{ "variant" : "Variant" }'

    def wordclass_choices(self):
        """Return JSON for wordclass choices"""

        # Get the list of choices for this field
        li = list(FieldChoice.objects.filter(field='WordClass', machine_value__lte=1)
                         .order_by('machine_value').values_list('id', 'name')) \
                  + list([(field_choice.id, field_choice.name) for field_choice in
                          FieldChoice.objects.filter(field='WordClass', machine_value__gt=1)
                         .order_by('name')])

        # Sort the list
        sorted_li = sorted(li, key=lambda x: x[1])

        # Put it in another format
        reformatted_li = [('_' + str(value), text) for value, text in sorted_li]

        return json.dumps(OrderedDict(reformatted_li))

    def semanticfield_choices(self):
        """Return JSON for semantic field choices"""

        d = dict()
        for sf in SemanticField.objects.all():
            d[sf.name] = sf.name
        return json.dumps(d)

    def derivationhistory_choices(self):
        """Return JSON for semantic field choices"""

        d = dict()
        for dh in DerivationHistory.objects.all():
            d[dh.name] = dh.name
        return json.dumps(d)

    def signlanguage_choices(self):
        """Return JSON for langauge choices"""

        d = dict()
        for l in SignLanguage.objects.all():
            d[l.name] = l.name

        return json.dumps(d)

    def dialect_choices(self):
        """Return JSON for dialect choices"""

        try:
            dataset = self.lemma.dataset
            try:
                signlanguage = dataset.signlanguage
            except:
                signlanguage = None
        except:
            dataset = None

        if signlanguage:
            possible_dialects = Dialect.objects.filter(signlanguage=signlanguage)
        elif dataset:
            possible_dialects = []
        else:
            possible_dialects = Dialect.objects.all()
        d = dict()
        for l in possible_dialects:
            dialect_name = l.signlanguage.name + "/" + l.name
            d[dialect_name] = dialect_name

        dict_list = list(d.items())
        sorted_dict_list = sorted(dict_list)
        first_element_sorted_dict_list = [x[0] for x in sorted_dict_list]

        return json.dumps(first_element_sorted_dict_list)

    def dataset_choices(self):

        d = dict()
        for s in Dataset.objects.all():
            d[s.acronym] = s.acronym

        return json.dumps(d)

    def get_annotationidglosstranslation_texts(self):
        d = dict()
        annotationidglosstranslations = self.annotationidglosstranslation_set.all()
        for translation in annotationidglosstranslations:
            d[translation.language.language_code_2char] = translation.text

        return d

    def tags(self):
        from tagging.models import Tag
        return Tag.objects.get_for_object(self)

# register Gloss for tags
try:
    tagging.register(Gloss)
except:
    pass


@receiver(pre_delete, sender=Gloss, dispatch_uid='gloss_delete_signal')
def save_info_about_deleted_gloss(sender, instance, using, **kwarsg):
    from signbank.tools import get_default_annotationidglosstranslation
    default_annotationidglosstranslation = get_default_annotationidglosstranslation(instance)

    deleted_gloss = DeletedGlossOrMedia()
    deleted_gloss.item_type = 'gloss'
    deleted_gloss.idgloss = instance.idgloss
    deleted_gloss.annotation_idgloss = default_annotationidglosstranslation
    deleted_gloss.old_pk = instance.pk
    deleted_gloss.save()


# We want to remember some stuff about deleted glosses
class DeletedGlossOrMedia(models.Model):
    item_type = models.CharField(max_length=5, choices=(('gloss', 'gloss'), ('image', 'image'), ('video', 'video')))
    idgloss = models.CharField("ID Gloss", max_length=50)
    annotation_idgloss = models.CharField("Annotation ID Gloss", max_length=30)
    old_pk = models.IntegerField()

    filename = models.CharField(max_length=100, blank=True)  # For media only

    deletion_date = models.DateField(default=date.today)


RELATION_ROLE_CHOICES = (('homonym', 'Homonym'),
                         ('synonym', 'Synonym'),
                         ('variant', 'Variant'),
                         ('antonym', 'Antonym'),
                         ('hyponym', 'Hyponym'),
                         ('hypernym', 'Hypernym'),
                         ('seealso', 'See Also'),
                         ('paradigm', 'Handshape Paradigm')
                         )

VARIANT_ROLE_CHOICES = (('variant', 'Variant'))


# this can be used for phonology and handshape fields
def fieldname_to_kind(fieldname):

    if fieldname in fieldname_to_kind_table.keys():
        field_kind = fieldname_to_kind_table[fieldname]
    else:
        print('fieldname not found in fieldname_to_kind_table: ', fieldname)
        field_kind = fieldname

    return field_kind


class Relation(models.Model):
    """A relation between two glosses"""

    source = models.ForeignKey(Gloss, related_name="relation_sources", on_delete=models.CASCADE)
    target = models.ForeignKey(Gloss, related_name="relation_targets", on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=RELATION_ROLE_CHOICES)

    class Admin:
        list_display = ['source', 'role', 'target']
        search_fields = ['source__idgloss', 'target__idgloss']

    class Meta:
        ordering = ['source']

    def get_reverse_role(role):
        if role == 'hyponym':
            return 'hypernym'
        elif role == 'hypernym':
            return 'hyponym'
        else:
            return role


class MorphologyDefinition(models.Model):
    """Tells something about morphology of a gloss"""

    parent_gloss = models.ForeignKey(Gloss, related_name="parent_glosses", on_delete=models.CASCADE)
    role = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                    limit_choices_to={'field': FieldChoice.MORPHOLOGYTYPE},
                                    field_choice_category=FieldChoice.MORPHOLOGYTYPE,
                                    verbose_name=_("Morphology Type"))
    morpheme = models.ForeignKey(Gloss, related_name="morphemes", on_delete=models.CASCADE)

    def __str__(self):
        return self.morpheme.idgloss

    def get_role(self):
        return self.role.name if self.role else self.role


class Morpheme(Gloss):
    """A morpheme definition uses all the fields of a gloss, but adds its own characteristics (#174)"""

    # Fields that are specific for morphemes, and not so much for 'sign-words' (=Gloss) as a whole
    # (1) optional morpheme-type field (not to be confused with MorphologyType from MorphologyDefinition)
    mrpType = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                       limit_choices_to={'field': FieldChoice.MORPHEMETYPE},
                                       field_choice_category=FieldChoice.MORPHEMETYPE,
                                       verbose_name=_("Has morpheme type"), related_name='morpheme_type')

    def __str__(self):
        """Morpheme string is like a gloss but with a marker identifying it as a morpheme"""
        # return "%s (%s)" % (self.idgloss, self.get_mrpType_display())
        # The display needs to be overrided to accomodate translations, the mrpType is done in adminviews
        # The idgloss field is no longer correct
        # We won't use this method in the interface but leave it for debugging purposes

        return self.idgloss

    def get_mrpType_display(self):
        # to avoid extra code in the template, return '-' if the type has not been set
        return self.mrpType.name if self.mrpType else '-'

    def get_handedness_display(self):
        return self.handedness.name if self.handedness else self.handedness

    def get_locprim_display(self):
        return self.locprim.name if self.locprim else self.locprim

    def admin_next_morpheme(self):
        """next morpheme in the admin view, shortcut for next_dictionary_morpheme with staff=True"""

        return self.next_dictionary_morpheme(True)

    def next_dictionary_morpheme(self, staff=False):
        """Find the next morpheme in dictionary order"""

        if staff:
            all_morphemes_ordered = Morpheme.objects.all().order_by('lemma')
        else:
            all_morphemes_ordered = Morpheme.objects.filter(inWeb__exact=True).order_by('lemma')

        if all_morphemes_ordered:

            foundit = False

            for morpheme in all_morphemes_ordered:
                if morpheme == self:
                    foundit = True
                elif foundit:
                    return morpheme
                    break

        else:
            return None

    def mrptype_choices(self):
        """Return JSON for mrptype choices"""

        # Get the list of choices for this field
        li = list(FieldChoice.objects.filter(field='MorphemeType', machine_value__lte=1)
                         .order_by('machine_value').values_list('id', 'name')) \
                  + list([(field_choice.id, field_choice.name) for field_choice in
                          FieldChoice.objects.filter(field='MorphemeType', machine_value__gt=1)
                         .order_by('name')])

        # Sort the list
        sorted_li = sorted(li, key=lambda x: x[1])

        # Put it in another format
        reformatted_li = [('_' + str(value), text) for value, text in sorted_li]

        return json.dumps(OrderedDict(reformatted_li))

    def abstract_meaning(self):
        # this is used for displaying morpheme keywords per language in the morpheme list view
        # all languages need to be represented for the template
        # languages not in the dataset translation languages are empty
        all_languages = Language.objects.all()
        if self.dataset:
            translation_languages = self.dataset.translation_languages.all()
        else:
            translation_languages = Language.objects.filter(id=get_default_language_id())
        abstract_meaning = []
        for language in all_languages:
            if language in translation_languages:
                translations = self.translation_set.filter(language=language).order_by('translation__index')
                abstract_meaning.append((language, translations))
            else:
                abstract_meaning.append((language, ''))
        return abstract_meaning

def generate_fieldname_to_kind_table():
    temp_field_to_kind_table = dict()
    for fieldname in ['semField', 'derivHist']:
        temp_field_to_kind_table[fieldname] = 'list'
    for f in Gloss._meta.fields:
        f_internal_type = f.get_internal_type()
        if f_internal_type in ['BooleanField', 'BooleanField']:
            temp_field_to_kind_table[f.name] = 'check'
        elif f_internal_type in ['CharField', 'TextField']:
            temp_field_to_kind_table[f.name] = 'text'
        elif f_internal_type in ['ForeignKey'] and f.name in ['domhndsh', 'subhndsh', 'final_domhndsh', 'final_subhndsh']:
            temp_field_to_kind_table[f.name] = 'list'
        elif f.name in ['semField', 'derivHist']:
            temp_field_to_kind_table[f.name] = 'list'
        elif hasattr(f, 'field_choice_category'):
            temp_field_to_kind_table[f.name] = 'list'
        else:
            temp_field_to_kind_table[f.name] = f_internal_type
    for f in Morpheme._meta.fields:
        f_internal_type = f.get_internal_type()
        if f_internal_type in ['BooleanField', 'BooleanField']:
            temp_field_to_kind_table[f.name] = 'check'
        elif f_internal_type in ['CharField', 'TextField']:
            temp_field_to_kind_table[f.name] = 'text'
        elif f_internal_type in ['ForeignKey'] and f.name in ['domhndsh', 'subhndsh', 'final_domhndsh', 'final_subhndsh']:
            temp_field_to_kind_table[f.name] = 'list'
        elif f.name in ['semField', 'derivHist']:
            temp_field_to_kind_table[f.name] = 'list'
        elif hasattr(f, 'field_choice_category'):
            temp_field_to_kind_table[f.name] = 'list'
        else:
            temp_field_to_kind_table[f.name] = f_internal_type
    for h in Handshape._meta.fields:
        h_internal_type = h.get_internal_type()
        if h.name not in temp_field_to_kind_table.keys():
            if h_internal_type in ['BooleanField', 'BooleanField']:
                temp_field_to_kind_table[h.name] = 'check'
            elif h_internal_type in ['CharField', 'TextField']:
                temp_field_to_kind_table[h.name] = 'text'
            elif hasattr(h, 'field_choice_category'):
                temp_field_to_kind_table[h.name] = 'list'
            else:
                temp_field_to_kind_table[h.name] = h_internal_type
        else:
            # field h already appears in the table
            if h_internal_type != temp_field_to_kind_table[h.name]:
                # does this happen?
                print('generate_fieldname_to_kind_table: identical fieldname in Gloss and Handshape with different kinds: ', h.name)
    for d in Definition._meta.fields:
        d_internal_type = d.get_internal_type()
        if d.name not in temp_field_to_kind_table.keys():
            if d_internal_type in ['BooleanField', 'BooleanField']:
                temp_field_to_kind_table[d.name] = 'check'
            elif d_internal_type in ['CharField', 'TextField']:
                temp_field_to_kind_table[d.name] = 'text'
            elif hasattr(d, 'field_choice_category'):
                temp_field_to_kind_table[d.name] = 'list'
            else:
                temp_field_to_kind_table[d.name] = d_internal_type
        else:
            # field h already appears in the table
            if d_internal_type != temp_field_to_kind_table[d.name]:
                # does this happen?
                print('generate_fieldname_to_kind_table: identical fieldname in Gloss or Handshape and Definition with different kinds: ', d.name)
    return temp_field_to_kind_table


fieldname_to_kind_table = generate_fieldname_to_kind_table()

class SimultaneousMorphologyDefinition(models.Model):
    parent_gloss = models.ForeignKey(Gloss, related_name='simultaneous_morphology', on_delete=models.CASCADE)
    role = models.CharField(max_length=100)
    morpheme = models.ForeignKey(Morpheme, related_name='glosses_containing', on_delete=models.CASCADE)

    def __str__(self):
        return self.parent_gloss.idgloss


class BlendMorphology(models.Model):
    parent_gloss = models.ForeignKey(Gloss, related_name='blend_morphology', on_delete=models.CASCADE)
    role = models.CharField(max_length=100)
    glosses = models.ForeignKey(Gloss, related_name='glosses_comprising', on_delete=models.CASCADE)

    def __str__(self):
        return self.parent_gloss.idgloss


class OtherMedia(models.Model):
    """Videos of or related to a gloss, often created by another project"""

    parent_gloss = models.ForeignKey(Gloss, on_delete=models.CASCADE)
    type = FieldChoiceForeignKey(FieldChoice, on_delete=models.SET_NULL, null=True,
                                    limit_choices_to={'field': FieldChoice.OTHERMEDIATYPE},
                                    field_choice_category=FieldChoice.OTHERMEDIATYPE,
                                    verbose_name=_("Type"), related_name='other_media')
    alternative_gloss = models.CharField(max_length=50)
    path = models.CharField(max_length=100)


    def get_othermedia_path(self, gloss_id, check_existence=False):
        # read only method
        """Returns a tuple (media_okay, path, filename) """
        # handles paths stored in OtherMedia objects created by legacy code that may have the wrong folder
        media_okay = True
        this_path = self.path
        import os
        norm_path = os.path.normpath(this_path)
        split_norm_path = norm_path.split(os.sep)
        if len(split_norm_path) == 1:
            # other media path is a filename
            path = 'dictionary/protected_media/othermedia/' + self.path
            media_okay = False
            other_media_filename = self.path
        elif len(split_norm_path) == 2 and split_norm_path[0] == str(gloss_id):
            # other media path is gloss_id / filename
            path = 'dictionary/protected_media/othermedia/' + self.path
            other_media_filename = split_norm_path[-1]
        else:
            # other media path is not a filename and not the correct folder, do not prefix it
            media_okay = False
            path = self.path
            other_media_filename = split_norm_path[-1]
        if media_okay:
            # self.path is okay, make sure it exists
            if check_existence:
                # check whether the file exists in the writable folder
                # NOTE: Here is a discrepancy with the setting OTHER_MEDIA_DIRECTORY, it ends with a /
                # os.path.exists needs a path, not a string of a path
                writable_location = os.path.join(WRITABLE_FOLDER,'othermedia',self.path)
                try:
                    imagefile_path_exists = os.path.exists(writable_location)
                except (UnicodeEncodeError, IOError, OSError):
                    # this is needed in case there is something wrong with the permissions
                    imagefile_path_exists = False
                if not imagefile_path_exists:
                    media_okay = False
        return media_okay, path, other_media_filename

class Dataset(models.Model):
    """A dataset, can be public/private and can be of only one SignLanguage"""
    name = models.CharField(unique=True, blank=False, null=False, max_length=60)
    is_public = models.BooleanField(default=False, help_text="Is this dataset public or private?")
    signlanguage = models.ForeignKey("SignLanguage", on_delete=models.CASCADE)
    translation_languages = models.ManyToManyField("Language", help_text="These languages are shown as options"
                                                                         "for translation equivalents.")
    default_language = models.ForeignKey('Language', on_delete=models.DO_NOTHING,
                                         related_name='datasets_with_default_language',
                                         null=True)
    description = models.TextField()
    conditions_of_use = models.TextField(blank=True, help_text="Conditions of Use. Content license."
                                                               "This is different than the software code license.")
    copyright = models.TextField(blank=True, help_text="Copyright. Content license."
                                                       "This is different than the software code license.")
    reference = models.TextField(blank=True, help_text="")
    acronym = models.CharField(max_length=10, blank=True, help_text="Abbreviation for the dataset")
    owners = models.ManyToManyField(User, help_text="Users responsible for the dataset content.")

    exclude_choices = models.ManyToManyField('FieldChoice', help_text="Exclude these field choices", blank=True)

    class Meta:
        permissions = (
            ('can_view_dataset', _('View dataset')),
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Keep original acronym for changes to GlossVideos
        self._initial = model_to_dict(self, fields=['acronym', 'default_language'])

    def __str__(self):
        return self.acronym

    def generate_short_name(self):

        CHARACTER_THRESHOLD = 15

        if len(self.acronym) <= CHARACTER_THRESHOLD:
            return self.acronym
        else:

            # Cut off last word
            if len(self.acronym.split()) > 1:
                result = ' '.join(self.acronym.split()[:-1])

                if len(result) <= CHARACTER_THRESHOLD:
                    return result
            else:
                result = self.acronym

            return result[:CHARACTER_THRESHOLD]

    def get_metadata_path(self, check_existance=True):
        """Returns the path within the writable and static folder"""
        metafile_name = self.acronym + '_metadata.csv'

        goal_string = WRITABLE_FOLDER + DATASET_METADATA_DIRECTORY + '/' + metafile_name

        if check_existance and os.path.exists(goal_string): #os.path.join(settings.WRITABLE_FOLDER, imagefile_path)):
            return goal_string

        return ''

    def metadata_url(self):
        metafile_name = self.acronym + '_metadata.csv'

        goal_string = DATASET_METADATA_DIRECTORY + '/' + metafile_name

        return goal_string

    def uploaded_eafs(self):

        # this is to move the file system commands out of models.py
        from signbank.frequency import uploaded_eaf_paths, eaf_file_from_paths

        eaf_paths = uploaded_eaf_paths(self.acronym)
        uploaded_eafs = eaf_file_from_paths(eaf_paths)

        uploaded_eafs.sort()

        return uploaded_eafs

    def count_glosses(self):

        count_glosses = Gloss.objects.filter(lemma__dataset_id=self.id).count()

        return count_glosses

    def get_users_who_can_view_dataset(self):

        all_users = User.objects.all().order_by('first_name')

        users_who_can_view_dataset = []
        import guardian
        from guardian.shortcuts import get_objects_for_user, get_users_with_perms
        users_who_can_access_me = get_users_with_perms(self, attach_perms=True, with_superusers=False,
                                                       with_group_users=False)
        for user in all_users:
            if user in users_who_can_access_me.keys():
                if 'can_view_dataset' in users_who_can_access_me[user] or 'view_dataset' in users_who_can_access_me[user]:
                    users_who_can_view_dataset.append(user)

        return users_who_can_view_dataset

    def get_users_who_can_change_dataset(self):

        all_users = User.objects.all().order_by('first_name')

        users_who_can_change_dataset = []
        import guardian
        from guardian.shortcuts import get_objects_for_user, get_users_with_perms
        users_who_can_access_me = get_users_with_perms(self, attach_perms=True, with_superusers=False,
                                                       with_group_users=False)
        for user in all_users:
            if user in users_who_can_access_me.keys():
                if 'change_dataset' in users_who_can_access_me[user]:
                    users_who_can_change_dataset.append(user)

        return users_who_can_change_dataset

    def frequency_regions(self):

        gf_objects = GlossFrequency.objects.filter(gloss__lemma__dataset=self)
        regions = gf_objects.values('speaker__location').distinct()
        frequency_regions = [ v['speaker__location'] for v in regions ]
        # the order of the reqions needs to be constant everywhere in the code. How?
        return frequency_regions

    def generate_frequency_dict(self):
        fields_to_map = FIELDS['phonology'] + FIELDS['semantics']

        fields_data = []
        for field in fields_to_map:
            gloss_field = Gloss._meta.get_field(field)
            if isinstance(gloss_field, models.ForeignKey) and gloss_field.related_model == Handshape:
                fields_data.append(
                    (field, gloss_field.verbose_name.title(), 'Handshape'))
            elif hasattr(gloss_field, 'field_choice_category'):
                fields_data.append((field, gloss_field.verbose_name.title(), gloss_field.field_choice_category))
            elif field == 'semField':
                fields_data.append((field, gloss_field.verbose_name.title(), 'SemField'))
            elif field == 'derivHist':
                fields_data.append((field, gloss_field.verbose_name.title(), 'derivHist'))
            # else:
            #     print('generate freq dict: ', field)

        # Sort the data by the translated verbose name field
        ordered_fields_data = sorted(fields_data, key=lambda x: x[1])
        frequency_lists_phonology_fields = OrderedDict()
        # To generate the correct order, iterate over the ordered fields data, which is ordered by translated verbose name
        for (f, field_verbose_name, fieldchoice_category) in ordered_fields_data:
            # Choices: the ones with machine_value 0 and 1 first, the rest is sorted by name, which is the translated name
            if fieldchoice_category == 'Handshape':
                choice_list_this_field = list(Handshape.objects.filter(machine_value__lte=1).order_by('machine_value')) \
                                         + list(Handshape.objects.filter(machine_value__gt=1).order_by('name'))
            elif fieldchoice_category == 'SemField':
                choice_list_this_field = list(SemanticField.objects.filter(machine_value__lte=1).order_by('machine_value')) \
                                         + list(SemanticField.objects.filter(machine_value__gt=1).order_by('name'))
            elif fieldchoice_category == 'derivHist':
                choice_list_this_field = list(DerivationHistory.objects.filter(machine_value__lte=1).order_by('machine_value')) \
                                         + list(DerivationHistory.objects.filter(machine_value__gt=1).order_by('name'))
            else:
                choice_list_this_field = list(FieldChoice.objects.filter(field=fieldchoice_category, machine_value__lte=1).order_by('machine_value')) \
                                        + list(FieldChoice.objects.filter(field=fieldchoice_category, machine_value__gt=1).order_by('name'))

            # Because we're dealing with multiple languages, we want the fields to be sorted for the language,
            # we maintain the order of the fields established for the choice_lists dict of field choice names
            choice_list_frequencies = OrderedDict()
            for fieldchoice in choice_list_this_field:
                # variable column is field.name
                variable_column = f
                if variable_column.startswith('semField') and fieldchoice.machine_value > 0:
                    variable_column_query = 'semField__machine_value__in'
                    try:
                        semantic_field = [sf.machine_value for sf in SemanticField.objects.filter(name__exact=fieldchoice.name)]
                        choice_list_frequencies[fieldchoice.name] = Gloss.objects.filter(lemma__dataset=self,
                                                                                         **{
                                                                                             variable_column_query: semantic_field}).count()
                    except ObjectDoesNotExist:
                        print('not found semantic choice, ignore: ', fieldchoice.name)
                        continue
                elif variable_column.startswith('derivHist') and fieldchoice.machine_value > 0:
                    variable_column_query = 'derivHist__machine_value__in'
                    try:
                        derivation_field = [sf.machine_value for sf in DerivationHistory.objects.filter(name__exact=fieldchoice.name)]
                        choice_list_frequencies[fieldchoice.name] = Gloss.objects.filter(lemma__dataset=self,
                                                                                         **{
                                                                                             variable_column_query: derivation_field}).count()
                    except ObjectDoesNotExist:
                        print('not found derivation history choice, ignore: ', fieldchoice.name)
                        continue
                # empty values can be either 0 or else null
                elif fieldchoice.machine_value == 0:
                    choice_list_frequencies[fieldchoice.name] = Gloss.objects.filter(Q(lemma__dataset=self),
                                                                                     Q(**{variable_column + '__isnull': True}) |
                                                                                     Q(**{variable_column: fieldchoice})).count()
                else:
                    choice_list_frequencies[fieldchoice.name] = Gloss.objects.filter(lemma__dataset=self,
                                                                                     **{variable_column: fieldchoice}).count()

            # the new frequencies for this field are added using the update method to insure the order is maintained
            frequency_lists_phonology_fields[f] = copy.deepcopy(choice_list_frequencies)

        return frequency_lists_phonology_fields


class UserProfile(models.Model):
    # This field is required.
    user = models.OneToOneField(User, related_name="user_profile_user", on_delete=models.CASCADE)

    # Other fields here
    last_used_language = models.CharField(max_length=20, default=settings.LANGUAGE_CODE)
    expiry_date = models.DateField(null=True, blank=True)
    number_of_logins = models.IntegerField(null=True, default=0)
    comments = models.CharField(max_length=500, null=True, blank=True)
    selected_datasets = models.ManyToManyField(Dataset)

    def save(self, *args, **kwargs):
        if not self.pk:
            try:
                p = UserProfile.objects.get(user=self.user)
                self.pk = p.pk
            except UserProfile.DoesNotExist:
                pass

        super(UserProfile, self).save(*args, **kwargs)

    def __str__(self):

        return 'Profile for ' + str(self.user)


def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


post_save.connect(create_user_profile, sender=User)


class Language(models.Model):
    """A written language, used for translations in written languages."""
    name = models.CharField(max_length=50)
    language_code_2char = models.CharField(max_length=7, unique=False, null=False, blank=False, help_text=_(
        """Language code (2 characters long) of a written language. This also includes codes of the form zh-Hans, cf. IETF BCP 47"""))
    language_code_3char = models.CharField(max_length=3, unique=False, null=False, blank=False, help_text=_(
        """ISO 639-3 language code (3 characters long) of a written language."""))
    description = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SemanticFieldTranslation(models.Model):

    semField = models.ForeignKey(SemanticField, on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)

    class Meta:
        unique_together = (("semField", "language", "name"),)


class DerivationHistoryTranslation(models.Model):

    derivHist = models.ForeignKey(DerivationHistory, on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)

    class Meta:
        unique_together = (("derivHist", "language", "name"),)



class AnnotationIdglossTranslation(models.Model):
    """An annotation ID Gloss"""
    text = models.CharField(_("Annotation ID Gloss"), max_length=30, help_text="""
        This is the name of a sign used by annotators when glossing the corpus in
        an ELAN annotation file.""")
    gloss = models.ForeignKey("Gloss", on_delete=models.CASCADE)
    language = models.ForeignKey("Language", on_delete=models.CASCADE)

    class Meta:
        unique_together = (("gloss", "language"),)

    def __init__(self, *args, **kwargs):
        if 'dataset' in kwargs:
            self.dataset = kwargs.pop('dataset')
        super(AnnotationIdglossTranslation, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        """
        1. Before an item is saved the language is checked against the languages of the dataset the gloss is in.
        2. The annotation idgloss translation text for a language must be unique within a dataset.
        Note that bulk updates will not use this method. Therefore, always iterate over a queryset when updating."""
        dataset = None
        if hasattr(self, 'dataset'):
            dataset = self.dataset
        elif hasattr(self.gloss, 'lemma') and hasattr(self.gloss.lemma, 'dataset'):
            dataset = self.gloss.lemma.dataset
        if dataset:
            # Before an item is saved the language is checked against the languages of the dataset the gloss is in.
            dataset_languages = dataset.translation_languages.all()
            if not self.language in dataset_languages:
                msg = "Language %s is not in the set of language of the dataset gloss %s belongs to" \
                      % (self.language.name, self.gloss.id)
                raise ValidationError(msg)

            # The annotation idgloss translation text for a language must be unique within a dataset.
            glosses_with_same_text = Gloss.objects.filter(annotationidglosstranslation__text__exact=self.text,
                                                          annotationidglosstranslation__language=self.language,
                                                          lemma__dataset=dataset)
            if not (
                    (len(glosses_with_same_text) == 1 and glosses_with_same_text[0] == self)
                    or glosses_with_same_text is None or len(glosses_with_same_text) == 0):
                msg = "The annotation idgloss translation text '%s' is not unique within dataset '%s' for gloss '%s'." \
                      % (self.text, dataset.acronym, self.gloss.id)
                raise ValidationError(msg)

        super(AnnotationIdglossTranslation, self).save(*args, **kwargs)


class LemmaIdgloss(models.Model):
    dataset = models.ForeignKey("Dataset", verbose_name=_("Dataset"), on_delete=models.CASCADE,
                                help_text=_("Dataset a lemma is part of"), null=True)

    class Meta:
        ordering = ['dataset__acronym']

    def __str__(self):
        translations = []
        count_dataset_languages = self.dataset.translation_languages.all().count() if self.dataset else 0
        for translation in self.lemmaidglosstranslation_set.all():
            if settings.SHOW_DATASET_INTERFACE_OPTIONS and count_dataset_languages > 1:
                translations.append("{}: {}".format(translation.language, translation.text))
            else:
                translations.append("{}".format(translation.text))
        return ", ".join(translations)


class LemmaIdglossTranslation(models.Model):
    """A Lemma ID Gloss"""
    text = models.CharField(_("Lemma ID Gloss translation"), max_length=30, help_text="""The lemma translation text.""")
    lemma = models.ForeignKey("LemmaIdgloss", on_delete=models.CASCADE)
    language = models.ForeignKey("Language", on_delete=models.CASCADE)

    class Meta:
        unique_together = (("lemma", "language"),)  # For each combination of lemma and language there is just one text.

    def __str__(self):
        return self.text

    def save(self, *args, **kwargs):
        """
        1. Before an item is saved the language is checked against the languages of the dataset the lemma is in.
        2. The lemma idgloss translation text for a language must be unique within a dataset.
        Note that bulk updates will not use this method. Therefore, always iterate over a queryset when updating."""
        dataset = self.lemma.dataset
        if dataset:
            # Before an item is saved the language is checked against the languages of the dataset the lemma is in.
            dataset_languages = dataset.translation_languages.all()
            if self.language not in dataset_languages:
                msg = "Language %s is not in the set of language of the dataset gloss %s belongs to" \
                      % (self.language.name, self.lemma.id)
                raise ValidationError(msg)

            # The lemma idgloss translation text for a language must be unique within a dataset.
            lemmas_with_same_text = dataset.lemmaidgloss_set.filter(lemmaidglosstranslation__text__exact=self.text,
                                                                    lemmaidglosstranslation__language=self.language)
            if lemmas_with_same_text.count() > 1:
                msg = "The lemma idgloss translation text '%s' is not unique within dataset '%s' for lemma '%s'." \
                      % (self.text, dataset.acronym, self.lemma.id)
                raise ValidationError(msg)

        super(LemmaIdglossTranslation, self).save(*args, **kwargs)

class GlossRevision(models.Model):

    gloss = models.ForeignKey("Gloss", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    time = models.DateTimeField()
    field_name = models.CharField(max_length=100)
    old_value = models.CharField(blank=True, max_length=100)
    new_value = models.CharField(blank=True, max_length=100)

    def __str__(self):

        #return str(self.user)
        return str(self.user) + " changed " + str(self.field_name) + " to " + str(self.new_value)

    @property
    def dataset(self):
        try:
            return self.gloss.lemma.dataset
        except (KeyError, AttributeError, LookupError):
            return None

class Corpus(models.Model):

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    speakers_are_cross_referenced = models.BooleanField()

class Document(models.Model):

    corpus = models.ForeignKey("Corpus", on_delete=models.CASCADE)
    identifier = models.CharField(max_length=100)
    creation_time = models.DateTimeField(blank=True)

class Speaker(models.Model):

    GENDER_CHOICES = (
        ('m', 'Male'),
        ('f', 'Female'),
        ('o', 'Other'),
    )
    HANDEDNESS_CHOICES = (
        ('r', 'Right'),
        ('l', 'Left'),
        ('a', 'Ambidextrous'),
    )

    identifier = models.CharField(max_length=100)
    gender = models.CharField(blank=True,choices=GENDER_CHOICES,max_length=1)
    age = models.IntegerField(blank=True)
    location = models.CharField(max_length=100)
    handedness = models.CharField(blank=True,choices=HANDEDNESS_CHOICES,max_length=1)

    def __str__(self):
        try:
            (participant, corpus) = self.identifier.rsplit('_', 1)
        except:
            participant = self.identifier
        return participant

    def participant(self):
        try:
            (participant, corpus) = self.identifier.rsplit('_', 1)
        except:
            participant = self.identifier
        return participant

class GlossFrequency(models.Model):

    speaker = models.ForeignKey("Speaker", on_delete=models.CASCADE)
    document = models.ForeignKey("Document", on_delete=models.CASCADE)
    gloss = models.ForeignKey("Gloss", on_delete=models.CASCADE)
    frequency = models.IntegerField()

    def __str__(self):

        return str(self.gloss.id) + ' ' + self.document.identifier + ' ' + self.speaker.identifier + ' ' + str(self.frequency)


class QueryParameter(models.Model):

    search_history = models.ForeignKey("SearchHistory", null=True, on_delete=models.CASCADE)
    # this parameter determines whether the key value has '[]' after the field name
    multiselect = models.BooleanField(_('Multiple Select'), default=True,
                                      help_text=_("Is this a multiselect parameter?"))

    def __str__(self):
        if hasattr(self, 'queryparameterfieldchoice'):
            field_choice = self.queryparameterfieldchoice
            glossFieldName = field_choice.display_verbose_fieldname()
            glossFieldValue = field_choice.fieldValue.name
        elif hasattr(self, 'queryparameterhandshape'):
            handshape = self.queryparameterhandshape
            glossFieldName = handshape.display_verbose_fieldname()
            glossFieldValue = handshape.fieldValue.name
        elif hasattr(self, 'queryparametersemanticfield'):
            semanticfield = self.queryparametersemanticfield
            glossFieldName = semanticfield.display_verbose_fieldname()
            glossFieldValue = semanticfield.fieldValue.name
        elif hasattr(self, 'queryparameterderivationhistory'):
            derivationhistory = self.queryparameterderivationhistory
            glossFieldName = derivationhistory.display_verbose_fieldname()
            glossFieldValue = derivationhistory.fieldValue.name
        elif hasattr(self, 'queryparameterboolean'):
            nullbooleanfield = self.queryparameterboolean
            glossFieldName = nullbooleanfield.display_verbose_fieldname()
            glossFieldValue = str(nullbooleanfield.fieldValue)
        elif hasattr(self, 'queryparametermultilingual'):
            multilingual = self.queryparametermultilingual
            glossFieldName = multilingual.display_verbose_fieldname()
            glossFieldValue = multilingual.fieldValue
        else:
            glossFieldName = "Unknown query parameter"
            glossFieldValue = "-"
        return glossFieldName + " " + glossFieldValue

    def is_fieldchoice(self):
        """Test if this instance is a Query Parameter Field Choice"""
        return hasattr(self, 'queryparameterfieldchoice')

    def is_handshape(self):
        """Test if this instance is a Query Parameter Handshape"""
        return hasattr(self, 'queryparameterhandshape')

    def is_semanticfield(self):
        """Test if this instance is a Query Parameter Semantic Field"""
        return hasattr(self, 'queryparametersemanticfield')

    def is_derivationhistory(self):
        """Test if this instance is a Query Parameter Derivation History"""
        return hasattr(self, 'queryparameterderivationhistory')

    def is_boolean(self):
        """Test if this instance is a Query Parameter Boolean"""
        return hasattr(self, 'queryparameterboolean')

    def is_multilingual(self):
        """Test if this instance is a Query Parameter Multilingual"""
        return hasattr(self, 'queryparametermultilingual')


class QueryParameterFieldChoice(QueryParameter):
    QUERY_FIELDS = [
        ('wordClass', 'wordClass'),
        ('handedness', 'handedness'),
        ('handCh', 'handCh'),
        ('relatArtic', 'relatArtic'),
        ('locprim', 'locprim'),
        ('relOriMov', 'relOriMov'),
        ('relOriLoc', 'relOriLoc'),
        ('oriCh', 'oriCh'),
        ('contType', 'contType'),
        ('movSh', 'movSh'),
        ('movDir', 'movDir'),
        ('namEnt', 'namEnt'),
        ('valence', 'valence'),
        # Definition Class
        ('definitionRole', 'definitionRole'),
        # MorphologyDefinition Class
        ('hasComponentOfType', 'hasComponentOfType')
    ]
    QUERY_FIELD_CATEGORY = [
        ('wordClass', 'WordClass'),
        ('handedness', 'Handedness'),
        ('handCh', 'HandshapeChange'),
        ('relatArtic', 'RelatArtic'),
        ('locprim', 'Location'),
        ('relOriMov', 'RelOriMov'),
        ('relOriLoc', 'RelOriLoc'),
        ('oriCh', 'OriChange'),
        ('contType', 'ContactType'),
        ('movSh', 'MovementShape'),
        ('movDir', 'MovementDir'),
        ('namEnt', 'NamedEntity'),
        ('valence', 'Valence'),
        # Definition Class
        ('definitionRole', 'NoteType'),
        # MorphologyDefinition Class
        ('hasComponentOfType', 'MorphologyType')
    ]
    fieldName = models.CharField(_("Field Name"), choices=QUERY_FIELDS, max_length=20)
    fieldValue = models.ForeignKey(FieldChoice, null=True, verbose_name=_("Field Value"), on_delete=models.CASCADE)

    def display_verbose_fieldname(self):
        glossFieldName = '-'
        if self.fieldName:
            if self.fieldName in ['definitionRole']:
                glossFieldName = Definition._meta.get_field('role').verbose_name.encode('utf-8').decode()
            elif self.fieldName in ['hasComponentOfType']:
                glossFieldName = MorphologyDefinition._meta.get_field('role').verbose_name.encode('utf-8').decode()
            else:
                glossFieldName = Gloss._meta.get_field(self.fieldName).verbose_name.encode('utf-8').decode()
        return glossFieldName

    def __str__(self):
        glossFieldName = '-'
        if self.fieldName:
            glossFieldName = self.display_verbose_fieldname()
        glossFieldValue = '-'
        if self.fieldValue:
            glossFieldValue = self.fieldValue.name
        return glossFieldName + " " + glossFieldValue

    def get_fieldValue_display(self):
        # no idea if this is called by Django, it overrides the built-in
        if not self.fieldValue:
            return ""
        return self.fieldValue.field + ': ' + self.fieldValue.name


class QueryParameterHandshape(QueryParameter):
    QUERY_FIELDS = [
        ('domhndsh', 'domhndsh'),
        ('subhndsh', 'subhndsh'),
        # ASL fields
        ('final_domhndsh', 'final_domhndsh'),
        ('final_subhndsh', 'final_subhndsh')
    ]
    fieldName = models.CharField(_("Handshape"), choices=QUERY_FIELDS, max_length=20)
    fieldValue = models.ForeignKey(Handshape, null=True, on_delete=models.CASCADE)

    def display_verbose_fieldname(self):
        glossFieldName = '-'
        if self.fieldName:
            glossFieldName = Gloss._meta.get_field(self.fieldName).verbose_name.encode('utf-8').decode()
        return glossFieldName

    def display_fieldvalue(self):
        glossFieldValue = '-'
        if self.fieldValue:
            glossFieldValue = self.fieldValue.name
        return glossFieldValue

    def __str__(self):
        glossFieldName = self.display_verbose_fieldname()
        glossFieldValue = self.display_fieldvalue()
        return glossFieldName + " " + glossFieldValue


class QueryParameterSemanticField(QueryParameter):
    QUERY_FIELDS = [
        ('semField', 'semField')
    ]
    fieldName = models.CharField(_("Semantic Field"), choices=QUERY_FIELDS, max_length=20)
    fieldValue = models.ForeignKey(SemanticField, null=True, on_delete=models.CASCADE)

    def display_verbose_fieldname(self):
        glossFieldName = '-'
        if self.fieldName:
            glossFieldName = Gloss._meta.get_field(self.fieldName).verbose_name.encode('utf-8').decode()
        return glossFieldName

    def __str__(self):
        glossFieldName = self.display_verbose_fieldname()
        glossFieldValue = '-'
        if self.fieldValue:
            glossFieldValue = self.fieldValue.name
        return glossFieldName + " " + glossFieldValue


class QueryParameterDerivationHistory(QueryParameter):
    QUERY_FIELDS = [
        ('derivHist', 'derivHist')
    ]
    fieldName = models.CharField(_("Derivation History"), choices=QUERY_FIELDS, max_length=20)
    fieldValue = models.ForeignKey(DerivationHistory, null=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "Query parameter derivation histories"

    def display_verbose_fieldname(self):
        glossFieldName = '-'
        if self.fieldName:
            glossFieldName = Gloss._meta.get_field(self.fieldName).verbose_name.encode('utf-8').decode()
        return glossFieldName

    def __str__(self):
        glossFieldName = self.display_verbose_fieldname()
        glossFieldValue = '-'
        if self.fieldValue:
            glossFieldValue = self.fieldValue.name
        return glossFieldName + " " + glossFieldValue


class QueryParameterBoolean(QueryParameter):
    # these are all fields of Gloss
    QUERY_FIELDS = [
        # Gloss model fields
        ('weakdrop', 'weakdrop'),
        ('weakprop', 'weakprop'),
        ('domhndsh_letter', 'domhndsh_letter'),
        ('domhndsh_number', 'domhndsh_number'),
        ('subhndsh_letter', 'subhndsh_letter'),
        ('subhndsh_number', 'subhndsh_number'),
        ('repeat', 'repeat'),
        ('altern', 'altern'),
        ('inWeb', 'inWeb'),
        ('isNew', 'isNew'),
        ('excludeFromEcv', 'excludeFromEcv'),
        # ASL fields
        ('oriChAbd', 'oriChAbd'),
        ('oriChFlex', 'oriChFlex'),
        # GlossSearchForm fields
        ('hasRelationToForeignSign', 'hasRelationToForeignSign'),
        ('defspublished', 'defspublished'),
        ('hasvideo', 'hasvideo'),
        ('hasothermedia', 'hasothermedia')
    ]

    fieldName = models.CharField(_("NullBooleanField"), choices=QUERY_FIELDS, max_length=30)
    fieldValue = models.BooleanField(_("Field Value"), null=True, blank=True)

    def display_verbose_fieldname(self):
        if self.fieldName in Gloss._meta.fields:
            glossFieldName = Gloss._meta.get_field(self.fieldName).verbose_name.encode('utf-8').decode()
        elif self.fieldName == 'defspublished':
            glossFieldName = _("All Definitions Published")
        elif self.fieldName == 'hasRelationToForeignSign':
            glossFieldName = _("Related to Foreign Sign")
        elif self.fieldName == 'hasvideo':
            glossFieldName = _('Has Video')
        else:
            glossFieldName = _('Has Other Media')
        # the str coercion is needed for type checking, otherwise it's a proxy
        return str(glossFieldName)

    def display_fieldvalue(self):
        if self.fieldName in ['weakdrop', 'weakprop']:
            if self.fieldValue is None:
                glossFieldValue = _('Neutral')
            elif self.fieldValue:
                glossFieldValue = _('Yes')
            else:
                glossFieldValue = _('No')
        elif self.fieldValue:
            glossFieldValue = _('True')
        else:
            glossFieldValue = _('False')
        # the str coercion is needed for type checking, otherwise it's a proxy
        return str(glossFieldValue)

    def __str__(self):
        glossFieldName = self.display_verbose_fieldname()
        glossFieldValue = self.display_fieldvalue()
        return glossFieldName + " " + glossFieldValue


class QueryParameterMultilingual(QueryParameter):
    # these are all fields stored as text in queries
    QUERY_FIELDS = [
        ('glosssearch', 'glosssearch'),
        ('lemma', 'lemma'),
        ('keyword', 'keyword'),
        # Tag, TaggedItem
        ('tags', 'tags'),
        # Note Contains
        ('definitionContains', 'definitionContains'),
        # Created By
        ('createdBy', 'createdBy'),
        # multilingual keywords
        ('translation', 'translation'),
        ('search', 'search'),
        # dates as strings
        ('createdBefore', 'createdBefore'),
        ('createdAfter', 'createdAfter')
    ]

    fieldName = models.CharField(_("Text Search Field"), choices=QUERY_FIELDS, max_length=20)
    fieldLanguage = models.ForeignKey(Language, on_delete=models.CASCADE)
    fieldValue = models.CharField(_("Text Search Value"), max_length=30)

    def display_verbose_fieldname(self):
        if self.fieldName == 'tags':
            searchFieldName = _('Tags')
        elif self.fieldName == 'definitionContains':
            searchFieldName = _('Note Contains')
        elif self.fieldName == 'createdBy':
            searchFieldName = _('Created By')
        elif self.fieldName == 'createdBefore':
            searchFieldName = _('Created Before')
        elif self.fieldName == 'createdAfter':
            searchFieldName = _('Created After')
        elif self.fieldName == 'translation':
            searchFieldName = _('Search Translation')
        elif self.fieldName == 'search':
            searchFieldName = _('Search Gloss')
        elif self.fieldName == 'glosssearch':
            searchFieldName = _('Annotation ID Gloss') + " (" + self.fieldLanguage.name + ")"
        elif self.fieldName == 'lemma':
            searchFieldName = _('Lemma ID Gloss') + " (" + self.fieldLanguage.name + ")"
        elif self.fieldName == 'keyword':
            searchFieldName = _('Translations') + " (" + self.fieldLanguage.name + ")"
        else:
            searchFieldName = self.fieldName
        return searchFieldName

    def __str__(self):
        searchFieldName = self.display_verbose_fieldname()
        return searchFieldName + " " + self.fieldValue


class SearchHistory(models.Model):
    queryDate = models.DateTimeField(_('Query Date'), auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parameters = models.ManyToManyField(QueryParameter, related_name='query_parameters')
    queryName = models.CharField(blank=True, max_length=50, help_text=_("Abbreviation for the query"))

    class Meta:
        verbose_name_plural = "Search histories"

    def __str__(self):
        query_name = self.queryName
        if not self.queryName:
            # if this has not been set, use the date
            query_name = self.queryDate
        return query_name + " (" + self.user.username + ")"

    def query_languages(self):
        multilingual_parameters = QueryParameterMultilingual.objects.filter(search_history=self)
        language_parameters = [p.fieldLanguage for p in multilingual_parameters
                               if p.fieldName not in ['tags', 'definitionContains',
                                                      'createdBy', 'createdBefore', 'createdAfter',
                                                      'translation', 'search']]
        query_languages = list(set(language_parameters))
        return query_languages


CATEGORY_MODELS_MAPPING = {
    'SemField': SemanticField,
    'derivHist': DerivationHistory,
    'Handshape': Handshape
}
