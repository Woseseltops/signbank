import signbank.settings
from signbank.settings.base import WSGI_FILE, WRITABLE_FOLDER, GLOSS_VIDEO_DIRECTORY, LANGUAGE_CODE
import os
import shutil
from html.parser import HTMLParser
from zipfile import ZipFile
import json
import re
from urllib.parse import quote
import csv
from django.db.models import Q
from django.http import QueryDict

from django.utils.translation import override, gettext_lazy as _, activate

from django.http import HttpResponse, HttpResponseRedirect

from signbank.dictionary.models import *
from signbank.dictionary.forms import *
from django.utils.dateformat import format
from django.core.exceptions import ObjectDoesNotExist, EmptyResultSet
from django.db import OperationalError, ProgrammingError
from django.db.models import CharField, TextField, Value as V
from django.db.models.fields import BooleanField, BooleanField

from django.urls import reverse
from tagging.models import TaggedItem, Tag

from guardian.shortcuts import get_objects_for_user


def get_two_letter_dir(idgloss):
    foldername = idgloss[:2]

    if len(foldername) == 1:
        foldername += '-'

    return foldername


def save_media(source_folder,language_code_3char,goal_folder,gloss,extension):
        
    #Add a dot before the extension if needed
    if extension[0] != '.':
        extension = '.' + extension

    #Figure out some names
    annotation_id = ""
    try:
        language = Language.objects.get(language_code_3char=language_code_3char)
    except ObjectDoesNotExist:
        # no language exists for this folder
        return False, False
    annotationidglosstranslations = gloss.annotationidglosstranslation_set.filter(language=language)
    if annotationidglosstranslations and len(annotationidglosstranslations) > 0:
        annotation_id = annotationidglosstranslations[0].text
    pk = str(gloss.pk)
    destination_folder = os.path.join(
        WRITABLE_FOLDER,
        goal_folder,
        gloss.lemma.dataset.acronym,
        get_two_letter_dir(gloss.idgloss)
    )

    #Create the necessary subfolder if needed
    if not os.path.isdir(destination_folder):
        os.mkdir(destination_folder)

    #Move the file
    source = source_folder+annotation_id+extension
    goal = os.path.join(destination_folder, annotation_id+'-'+pk+extension)

    if os.path.isfile(goal):
        overwritten = True
    else:
        overwritten = False

    try:
        shutil.copyfile(source,goal)
        was_allowed = True
    except IOError:
        was_allowed = False

    try:
        os.remove(source)
    except OSError:
        pass

    return overwritten,was_allowed

def unescape(string):

    return HTMLParser().unescape(string)

class MachineValueNotFoundError(Exception):
    pass

table_column_name_lemma_id_gloss_translations = {}

#See if there are any languages there, but don't crash if there isn't even a table
try:
    for language in Language.objects.all():
        lemmaidgloss_comumn_name = "Lemma ID Gloss (%s)" % (getattr(language,settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English']))
        table_column_name_lemma_id_gloss_translations[language.language_code_2char] = lemmaidgloss_comumn_name
except (OperationalError, ProgrammingError) as e:
    pass

def create_gloss_from_valuedict(valuedict,dataset,row_nr,earlier_creation_same_csv, earlier_creation_annotationidgloss, earlier_creation_lemmaidgloss):

    errors_found = []
    new_gloss = []
    already_exists = []
    global table_column_name_lemma_id_gloss_translations

    #Create an overview of all fields, sorted by their human name
    with override(LANGUAGE_CODE):
        empty_lemma_translation = False
        existing_glosses = {}
        existing_lemmas = {}
        existing_lemmas_list = []
        new_lemmas = {}
        lemmaidglosstranslations = {}
        annotationidglosstranslations = {}
        translation_languages = dataset.translation_languages.all()
        for language in translation_languages:

            lemmaidgloss_comumn_name = "Lemma ID Gloss (%s)" % (getattr(language,settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English']))

            if lemmaidgloss_comumn_name in valuedict:
                lemmaidglosstranslation_text = valuedict[lemmaidgloss_comumn_name].strip()
                lemmaidglosstranslations[language.language_code_2char] = lemmaidglosstranslation_text

                lemmatranslation_for_this_text_language = LemmaIdglossTranslation.objects.filter(lemma__dataset=dataset,
                                                                                   language=language, text__exact=lemmaidglosstranslation_text)
                if lemmatranslation_for_this_text_language:
                    one_lemma = lemmatranslation_for_this_text_language[0].lemma
                    existing_lemmas[language.language_code_2char] = one_lemma
                    if not one_lemma in existing_lemmas_list:
                        existing_lemmas_list.append(one_lemma)
                elif not lemmaidglosstranslation_text:
                    empty_lemma_translation = True
                else:
                    new_lemmas[language.language_code_2char] = lemmaidglosstranslation_text

            column_name = "Annotation ID Gloss (%s)" % (getattr(language,settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English']))
            if column_name in valuedict:
                annotationidglosstranslation_text = valuedict[column_name].strip()
                if annotationidglosstranslation_text:
                    annotationidglosstranslations[language.language_code_2char] = annotationidglosstranslation_text

                    # The annotation idgloss translation text for a language must be unique within a dataset.
                    glosses_with_same_text = Gloss.objects.filter(lemma__dataset=dataset,
                                                                  annotationidglosstranslation__text__exact=annotationidglosstranslation_text,
                                                                  annotationidglosstranslation__language=language)
                    if len(glosses_with_same_text) > 0:
                        existing_glosses[language.language_code_2char] = glosses_with_same_text
                else:
                    error_string = 'Row ' + str(row_nr + 1) + ' has an empty ' + column_name
                    errors_found += [error_string]
            else:
                print('column name not in value dict: ', column_name)

        if existing_glosses:
            existing_gloss_set = set()
            for language_code_2char,glosses in existing_glosses.items():
                for gloss in glosses:
                    if gloss not in existing_gloss_set:
                        gloss_dict = {
                             'gloss_pk': gloss.pk,
                             'dataset': gloss.dataset
                        }
                        annotationidglosstranslation_dict = {}
                        for lang in gloss.lemma.dataset.translation_languages.all():
                            language_name = getattr(language,settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English'])
                            annotationidglosstranslation_text = valuedict["Annotation ID Gloss (%s)" % (language_name) ]
                            annotationidglosstranslation_dict[lang.language_code_2char] = annotationidglosstranslation_text
                        gloss_dict['annotationidglosstranslations'] = annotationidglosstranslation_dict

                        lemmaidglosstranslation_dict = {}
                        for lang in gloss.lemma.dataset.translation_languages.all():
                            language_name = getattr(language,settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English'])
                            lemmaidglosstranslation_text = valuedict["Lemma ID Gloss (%s)" % (language_name) ]
                            lemmaidglosstranslation_dict[lang.language_code_2char] = lemmaidglosstranslation_text
                        gloss_dict['lemmaidglosstranslations'] = lemmaidglosstranslation_dict
                        already_exists.append(gloss_dict)
                        existing_gloss_set.add(gloss)
        else:
            gloss_dict = {'gloss_pk' : str(row_nr + 1), 'dataset': dataset }
            trans_languages = [ l for l in dataset.translation_languages.all() ]
            annotationidglosstranslation_dict = {}
            for language in trans_languages:
                language_name = getattr(language, settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English'])
                annotationidglosstranslation_text = valuedict["Annotation ID Gloss (%s)" % (language_name) ]
                annotationidglosstranslation_dict[language.language_code_2char] = annotationidglosstranslation_text

                if earlier_creation_annotationidgloss and \
                        language.language_code_2char in earlier_creation_annotationidgloss.keys() and \
                        annotationidglosstranslation_text in earlier_creation_annotationidgloss[language.language_code_2char]:
                    error_string = 'Row ' + str(row_nr + 1) + ' contains a duplicate Annotation ID Gloss for '+ language_name +'.'
                    errors_found += [error_string]

                if not earlier_creation_annotationidgloss or (
                        language.language_code_2char not in earlier_creation_annotationidgloss.keys()):
                    earlier_creation_annotationidgloss[language.language_code_2char] = []
                earlier_creation_annotationidgloss[language.language_code_2char].append(annotationidglosstranslation_text)

            gloss_dict['annotationidglosstranslations'] = annotationidglosstranslation_dict

            lemmaidglosstranslation_dict = {}
            for language in trans_languages:
                language_name = getattr(language, settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English'])
                lemmaidglosstranslation_text = valuedict["Lemma ID Gloss (%s)" % (language_name) ]
                lemmaidglosstranslation_dict[language.language_code_2char] = lemmaidglosstranslation_text

            gloss_dict['lemmaidglosstranslations'] = lemmaidglosstranslation_dict
            new_gloss.append(gloss_dict)

        if len(existing_lemmas_list) > 0:

            if len(existing_lemmas_list) > 1:
                print('TOOLS more than one existing lemma in row ', str(row_nr+1))
            elif empty_lemma_translation:
                print('TOOLS exactly one lemma matches, but one of the translations in the csv is empty')
            if len(new_lemmas.keys()) and len(existing_lemmas.keys()):
                print('TOOLS existing and new lemmas in row ', str(row_nr+1))

        range_of_earlier_creation = [ v for (i,v) in earlier_creation_same_csv.items() ]
        if earlier_creation_same_csv and new_gloss in range_of_earlier_creation:
            error_string = 'Row ' + str(row_nr + 1) + ' is a duplicate gloss creation.'
            errors_found += [error_string]

    # save the parameters for the new gloss under the row number
    # make sure this gloss isn't being created twice
    if len(errors_found) == 0 and len(already_exists) == 0:
        earlier_creation_same_csv[str(row_nr+1)] = new_gloss
        earlier_creation_lemmaidgloss[str(row_nr+1)] = lemmaidglosstranslations

    return (new_gloss, already_exists, errors_found, earlier_creation_same_csv, earlier_creation_annotationidgloss, earlier_creation_lemmaidgloss)

def compare_valuedict_to_gloss(valuedict,gloss_id,my_datasets, nl, earlier_updates_same_csv, earlier_updates_lemmaidgloss):
    """Takes a dict of arbitrary key-value pairs, and compares them to a gloss"""

    errors_found = []
    differences = []

    try:
        gloss = Gloss.objects.select_related().get(pk=gloss_id)
    except ObjectDoesNotExist as e:

        e = 'Could not find gloss for ID ' + str(gloss_id)
        errors_found.append(e)
        return (differences, errors_found, earlier_updates_same_csv, earlier_updates_lemmaidgloss)

    if gloss_id in earlier_updates_same_csv:
        e = 'Signbank ID (' + str(gloss_id) + ') found in multiple rows (Row ' + str(nl + 1) + ').'
        errors_found.append(e)
        return (differences, errors_found, earlier_updates_same_csv, earlier_updates_lemmaidgloss)
    else:
        earlier_updates_same_csv.append(gloss_id)
    column_name_error = False
    tag_name_error = False
    all_tags = [t.name for t in Tag.objects.all()]
    all_tags_display = ', '.join([t.replace('_',' ') for t in all_tags])
    note_type_error = False
    note_tuple_error = False
    activate(LANGUAGES[0][0])
    note_role_choices = FieldChoice.objects.filter(field__iexact='NoteType')
    all_notes = [ n.name for n in note_role_choices]
    all_notes_display = ', '.join(all_notes)
    # this is used to speedup matching updates to Notes
    # it allows the type of note to be in either English or Dutch in the CSV file
    note_reverse_translation = {}
    for nrc in note_role_choices:
        note_reverse_translation[nrc.name] = nrc.machine_value
    note_translations = {}
    for nrc in note_role_choices:
        note_translations[str(nrc.machine_value)] = nrc.name

    #Create an overview of all fields, sorted by their human name
    with override(LANGUAGE_CODE):

        default_annotationidglosstranslation = get_default_annotationidglosstranslation(gloss)

        # There are too many to show the user!
        # allowed_column_names = [ str(f.verbose_name) for f in Gloss._meta.fields ]
        # allowed_columns = ', '.join(allowed_column_names)

        fields = {field.verbose_name: field for field in Gloss._meta.fields if field.name not in FIELDS['frequency']}

        columnheaders = fields.keys()

        columns_to_skip = {field.verbose_name: field for field in Gloss._meta.fields if field.name in FIELDS['frequency']}

        if gloss.lemma.dataset:
            current_dataset = gloss.lemma.dataset.acronym
        else:
            # because of legacy code, the current dataset might not have been set
            current_dataset = 'None'

        #Go through all values in the value dict, looking for differences with the gloss
        for human_key, new_human_value in valuedict.items():

            if human_key in columns_to_skip.keys():
                continue

            new_human_value_list = []

            if new_human_value:
                new_human_value_list = [v.strip() for v in new_human_value.split(',')]

            new_human_value = new_human_value.strip()

            #If these are not fields, but relations to other parts of the database, compare complex values
            if human_key == 'Signbank ID':
                continue

            annotation_idgloss_key_prefix = "Annotation ID Gloss ("
            if human_key.startswith(annotation_idgloss_key_prefix):
                language_name_column = settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English']
                language_name = human_key[len(annotation_idgloss_key_prefix):-1]
                languages = Language.objects.filter(**{language_name_column:language_name})
                if languages:
                    language = languages[0]
                    annotation_idglosses = gloss.annotationidglosstranslation_set.filter(language=language)
                    if annotation_idglosses:
                        annotation_idgloss_string = annotation_idglosses[0].text

                        if annotation_idgloss_string != new_human_value and new_human_value != 'None' and new_human_value != '':
                            glosses_with_same_annotation = Gloss.objects.filter(
                                annotationidglosstranslation__text__exact=new_human_value,
                                annotationidglosstranslation__language=language,
                                lemma__dataset=gloss.lemma.dataset).count()

                            if glosses_with_same_annotation:
                                error_string = 'ERROR: Signbank ID (' + str(gloss_id) \
                                               + ')  key value already exists: ' + human_key + ': ' + str(new_human_value)
                                errors_found += [error_string]

                            else:
                                differences.append({'pk': gloss_id,
                                                    'dataset': current_dataset,
                                                    'annotationidglosstranslation': default_annotationidglosstranslation,
                                                    'machine_key': human_key,
                                                    'human_key': human_key,
                                                    'original_machine_value': annotation_idgloss_string,
                                                    'original_human_value': annotation_idgloss_string,
                                                    'new_machine_value': new_human_value,
                                                    'new_human_value': new_human_value})
                continue

            lemma_idgloss_key_prefix = "Lemma ID Gloss ("
            if human_key.startswith(lemma_idgloss_key_prefix):
                language_name_column = settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English']
                language_name = human_key[len(lemma_idgloss_key_prefix):-1]
                languages = Language.objects.filter(**{language_name_column:language_name})
                if languages:
                    language = languages[0]
                    lemma_idglosses = gloss.lemma.lemmaidglosstranslation_set.filter(language=language)
                    if lemma_idglosses:
                        lemma_idgloss_string = lemma_idglosses[0].text
                    else:
                        # lemma not set
                        lemma_idgloss_string = ''
                    if lemma_idgloss_string != new_human_value and new_human_value != 'None' and new_human_value != '':
                        error_string = 'ERROR: Attempt to update Lemma ID Gloss translations: ' + human_key
                        errors_found += [error_string]
                continue

            keywords_key_prefix = "Keywords ("
            if human_key.startswith(keywords_key_prefix):
                language_name_column = settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English']
                language_name = human_key[len(keywords_key_prefix):-1]
                languages = Language.objects.filter(**{language_name_column:language_name})
                if languages:
                    language = languages[0]
                    translations = [t.translation.text for t in gloss.translation_set.filter(language=language).order_by('translation__text')]
                    current_keyword_string = ", ".join(translations)
                else:
                    error_string = 'ERROR: Non-existant language specified for Keywords column: ' + human_key
                    errors_found += [error_string]

                if current_keyword_string != new_human_value and new_human_value != 'None' and new_human_value != '':
                    differences.append({'pk':gloss_id,
                                        'dataset': current_dataset,
                                        'annotationidglosstranslation':default_annotationidglosstranslation,
                                        'machine_key':human_key,
                                        'human_key':human_key,
                                        'original_machine_value':current_keyword_string,
                                        'original_human_value':current_keyword_string,
                                        'new_machine_value':new_human_value,
                                        'new_human_value':new_human_value})
                continue

            elif human_key == 'SignLanguages':

                if new_human_value == 'None' or new_human_value == '':
                    continue

                current_signlanguages_string = str(', '.join([str(lang.name) for lang in gloss.signlanguage.all()]))

                (found, not_found, errors) = check_existance_signlanguage(gloss, new_human_value_list)

                if len(errors):
                    errors_found += errors

                if current_signlanguages_string != new_human_value:
                    differences.append({'pk':gloss_id,
                                        'dataset': current_dataset,
                                        'annotationidglosstranslation':default_annotationidglosstranslation,
                                        'machine_key':human_key,
                                        'human_key':human_key,
                                        'original_machine_value':current_signlanguages_string,
                                        'original_human_value':current_signlanguages_string,
                                        'new_machine_value':new_human_value,
                                        'new_human_value':new_human_value})
                continue

            elif human_key == 'Dialects':
                if new_human_value == 'None' or new_human_value == '':
                    continue

                current_dialects_string = str(', '.join([str(dia.name) for dia in gloss.dialect.all()]))

                (found, not_found, errors) = check_existence_dialect(gloss, new_human_value_list)

                if len(errors):
                    errors_found += errors

                elif current_dialects_string != new_human_value:
                    differences.append({'pk': gloss_id,
                                        'dataset': current_dataset,
                                        'annotationidglosstranslation':default_annotationidglosstranslation,
                                        'machine_key': human_key,
                                        'human_key': human_key,
                                        'original_machine_value': current_dialects_string,
                                        'original_human_value': current_dialects_string,
                                        'new_machine_value': new_human_value,
                                        'new_human_value': new_human_value})
                continue

            elif human_key == 'Dataset' or human_key == 'Glosses dataset':

                # cach legacy value
                if human_key == 'Glosses dataset':
                    human_key = 'Dataset'
                if new_human_value == 'None' or new_human_value == '':
                    # This check assumes that if the Dataset column is empty, it means no change
                    # Since we already know the id of the gloss, we keep the original dataset
                    # To be safe, confirm the original dataset is not empty, to catch legacy code
                    if not current_dataset or current_dataset == 'None' or current_dataset == None:
                        # Dataset must be non-empty to create a new gloss
                        error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(gloss_id) + '), Dataset must be non-empty. There is currently no dataset defined for this gloss.'

                        errors_found += [error_string]
                    continue

                # if we get to here, the user has specificed a new value for the dataset
                if new_human_value in my_datasets:
                    if current_dataset != new_human_value:
                        differences.append({'pk': gloss_id,
                                            'dataset': current_dataset,
                                            'annotationidglosstranslation':default_annotationidglosstranslation,
                                            'machine_key': human_key,
                                            'human_key': human_key,
                                            'original_machine_value': current_dataset,
                                            'original_human_value': current_dataset,
                                            'new_machine_value': new_human_value,
                                            'new_human_value': new_human_value})
                else:
                    error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(
                        gloss_id) + '), could not find ' + str(new_human_value) + ' for ' + human_key

                    errors_found += [error_string]

                continue

            elif human_key == 'Relations to other signs':
                if new_human_value == 'None' or new_human_value == '':
                    continue

                relations = [(relation.role, str(relation.target.id)) for relation in gloss.relation_sources.all()]

                # sort tuples on other gloss to allow comparison with imported values

                sorted_relations = sorted(relations, key=lambda tup: tup[1])

                relations_with_categories = []
                for rel_cat in sorted_relations:
                    relations_with_categories.append(':'.join(rel_cat))
                current_relations_string = ",".join(relations_with_categories)

                (checked_new_human_value, errors) = check_existance_relations(gloss, relations_with_categories, new_human_value_list)

                if len(errors):
                    errors_found += errors

                elif current_relations_string != checked_new_human_value:
                    differences.append({'pk': gloss_id,
                                        'dataset': current_dataset,
                                        'annotationidglosstranslation':default_annotationidglosstranslation,
                                        'machine_key': human_key,
                                        'human_key': human_key,
                                        'original_machine_value': current_relations_string,
                                        'original_human_value': current_relations_string,
                                        'new_machine_value': checked_new_human_value,
                                        'new_human_value': checked_new_human_value})
                continue

            elif human_key == 'Relations to foreign signs':
                if new_human_value == 'None' or new_human_value == '':
                    continue

                relations = [(str(relation.loan), relation.other_lang, relation.other_lang_gloss)
                             for relation in gloss.relationtoforeignsign_set.all().order_by('other_lang_gloss')]

                relations_with_categories = []
                for rel_cat in relations:
                    relations_with_categories.append(':'.join(rel_cat))
                current_relations_foreign_string = ",".join(relations_with_categories)

                (checked_new_human_value, errors) = check_existance_foreign_relations(gloss, relations_with_categories, new_human_value_list)

                if len(errors):
                    errors_found += errors

                elif current_relations_foreign_string != checked_new_human_value:
                    differences.append({'pk': gloss_id,
                                        'dataset': current_dataset,
                                        'annotationidglosstranslation':default_annotationidglosstranslation,
                                        'machine_key': human_key,
                                        'human_key': human_key,
                                        'original_machine_value': current_relations_foreign_string,
                                        'original_human_value': current_relations_foreign_string,
                                        'new_machine_value': checked_new_human_value,
                                        'new_human_value': checked_new_human_value})
                continue

            elif human_key == 'Sequential Morphology':
                if new_human_value == 'None' or new_human_value == '':
                    continue

                morphemes = [str(morpheme.morpheme.id) for morpheme in
                             MorphologyDefinition.objects.filter(parent_gloss=gloss)]
                morphemes_string = ", ".join(morphemes)

                (found, not_found, errors) = check_existance_sequential_morphology(gloss, new_human_value_list)

                if len(errors):
                    errors_found += errors

                elif morphemes_string != new_human_value:
                    differences.append({'pk': gloss_id,
                                        'dataset': current_dataset,
                                        'annotationidglosstranslation':default_annotationidglosstranslation,
                                        'machine_key': human_key,
                                        'human_key': human_key,
                                        'original_machine_value': morphemes_string,
                                        'original_human_value': morphemes_string,
                                        'new_machine_value': new_human_value,
                                        'new_human_value': new_human_value})
                continue

            elif human_key == 'Simultaneous Morphology':
                if new_human_value == 'None' or new_human_value == '':
                    continue

                morphemes = [(str(m.morpheme.id), m.role) for m in gloss.simultaneous_morphology.all()]
                sim_morphs = []
                for m in morphemes:
                    sim_morphs.append(':'.join(m))
                simultaneous_morphemes = ','.join(sim_morphs)

                (checked_new_human_value, errors) = check_existance_simultaneous_morphology(gloss, new_human_value_list)

                if len(errors):
                    errors_found += errors

                elif simultaneous_morphemes != checked_new_human_value:
                    differences.append({'pk': gloss_id,
                                        'dataset': current_dataset,
                                        'annotationidglosstranslation':default_annotationidglosstranslation,
                                        'machine_key': human_key,
                                        'human_key': human_key,
                                        'original_machine_value': simultaneous_morphemes,
                                        'original_human_value': simultaneous_morphemes,
                                        'new_machine_value': checked_new_human_value,
                                        'new_human_value': checked_new_human_value})
                continue

            elif human_key == 'Blend Morphology':
                if new_human_value == 'None' or new_human_value == '':
                    continue

                morphemes = [(str(m.glosses.id), m.role) for m in gloss.blend_morphology.all()]

                ble_morphs = []
                for m in morphemes:
                    ble_morphs.append(':'.join(m))
                blend_morphemes = ','.join(ble_morphs)

                (checked_new_human_value, errors) = check_existance_blend_morphology(gloss, new_human_value_list)

                if len(errors):
                    errors_found += errors

                elif blend_morphemes != checked_new_human_value:
                    differences.append({'pk': gloss_id,
                                        'dataset': current_dataset,
                                        'annotationidglosstranslation':default_annotationidglosstranslation,
                                        'machine_key': human_key,
                                        'human_key': human_key,
                                        'original_machine_value': blend_morphemes,
                                        'original_human_value': blend_morphemes,
                                        'new_machine_value': checked_new_human_value,
                                        'new_human_value': checked_new_human_value})
                continue

            elif human_key == 'Tags':
                if new_human_value == 'None' or new_human_value == '':
                    continue

                tags_of_gloss = TaggedItem.objects.filter(object_id=gloss_id)
                tag_names_of_gloss = []
                for t_obj in tags_of_gloss:
                    tag_id = t_obj.tag_id
                    tag_name = Tag.objects.get(id=tag_id)
                    tag_names_of_gloss += [str(tag_name)]
                tag_names_of_gloss = sorted(tag_names_of_gloss)

                tag_names = ", ".join(tag_names_of_gloss)

                tag_names_display = [ t.replace('_',' ') for t in tag_names_of_gloss ]
                tag_names_display = ', '.join(tag_names_display)

                new_human_value_list = [v.replace(' ', '_') for v in new_human_value_list]

                new_human_value_list_no_dups = list(set(new_human_value_list))
                sorted_new_tags = sorted(new_human_value_list_no_dups)

                # check for non-existant tags
                for t in sorted_new_tags:
                    if t in all_tags:
                        pass
                    else:
                        error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(
                            gloss_id) + '), a new Tag name was found: ' + t.replace('_',' ') + '.'

                        errors_found += [error_string]
                        if not tag_name_error:
                            error_string = 'Current tag names are: ' + all_tags_display + '.'
                            errors_found += [error_string]
                            tag_name_error = True


                new_tag_names_display = [ t.replace('_',' ') for t in sorted_new_tags ]
                new_tag_names_display = ', '.join(new_tag_names_display)

                sorted_new_tags = ", ".join(sorted_new_tags)

                if tag_names != sorted_new_tags:
                    differences.append({'pk': gloss_id,
                                        'dataset': current_dataset,
                                        'annotationidglosstranslation':default_annotationidglosstranslation,
                                        'machine_key': human_key,
                                        'human_key': human_key,
                                        'original_machine_value': tag_names_display,
                                        'original_human_value': tag_names_display,
                                        'new_machine_value': new_tag_names_display,
                                        'new_human_value': new_tag_names_display})
                continue

            elif human_key == 'Notes':

                if new_human_value == 'None' or new_human_value == '':
                    continue

                sorted_notes_display = get_notes_as_string(gloss)

                (sorted_new_notes_display, new_note_errors, note_type_error, note_tuple_error) = \
                            check_existence_notes(gloss, new_human_value, note_type_error, note_tuple_error, default_annotationidglosstranslation)

                if len(new_note_errors):
                    errors_found += new_note_errors
                elif sorted_notes_display != sorted_new_notes_display:
                    differences.append({'pk': gloss_id,
                                        'dataset': current_dataset,
                                        'annotationidglosstranslation':default_annotationidglosstranslation,
                                        'machine_key': human_key,
                                        'human_key': human_key,
                                        'original_machine_value': sorted_notes_display,
                                        'original_human_value': sorted_notes_display,
                                        'new_machine_value': sorted_new_notes_display,
                                        'new_human_value': sorted_new_notes_display})
                continue



            #If not, find the matching field in the gloss, and remember its 'real' name
            try:
                field = fields[human_key]
                machine_key = field.name

            except KeyError:
                # Signbank ID is skipped, for this purpose it was popped from the fields to compare
                # Skip above fields with complex values: Keywords, Signlanguages, Dialects, Relations to other signs, Relations to foreign signs, Morphology.

                error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(
                    gloss_id) + '), could not identify column name: ' + str(human_key)

                errors_found += [error_string]

                if not column_name_error:
                    # error_string = 'Allowed column names are: ' + allowed_columns
                    error_string = 'HINT: Try exporting a CSV file to see what column names can be used.'
                    errors_found += [error_string]
                    column_name_error = True

                continue

            #Try to translate the value to machine values if needed
            if hasattr(field, 'field_choice_category'):
                if new_human_value in ['', '0', ' ', None, 'None']:
                    new_human_value = '-'

                try:
                    field_choice = FieldChoice.objects.get(name=new_human_value, field=field.field_choice_category)
                    new_machine_value = field_choice.machine_value
                except ObjectDoesNotExist:
                    new_machine_value = None
                    error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(
                        gloss_id) + '), could not find option ' + str(new_human_value) + ' for ' + human_key

                    errors_found += [error_string]
                    continue

            #Do something special for integers and booleans
            elif field.__class__.__name__ == 'IntegerField':

                try:
                    new_machine_value = int(new_human_value)
                except ValueError:
                    new_human_value = 'None'
                    new_machine_value = None
            elif field.__class__.__name__ == 'BooleanField':

                new_human_value_lower = new_human_value.lower()
                if new_human_value_lower == 'neutral' and (field.name in settings.HANDEDNESS_ARTICULATION_FIELDS):
                    new_machine_value = None
                elif new_human_value_lower in ['true', 'yes', '1']:
                    new_machine_value = True
                    new_human_value = 'True'
                elif new_human_value_lower == 'none':
                    new_machine_value = None
                elif new_human_value_lower in ['false', 'no', '0']:
                    new_machine_value = False
                    new_human_value = 'False'
                else:
                    # Boolean expected
                    error_string = ''
                    # If the new value is empty, don't count this as a type error, error_string is generated conditionally
                    if field.name in settings.HANDEDNESS_ARTICULATION_FIELDS:
                        if new_human_value != None and new_human_value != '' and new_human_value != 'None':
                            error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(gloss_id) + '), value ' + str(new_human_value) + ' for ' + human_key + ' should be a Boolean or Neutral.'
                    else:
                        if new_human_value != None and new_human_value != '' and new_human_value != 'None':
                            error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(gloss_id) + '), value ' + str(new_human_value) + ' for ' + human_key + ' is not a Boolean.'

                    if error_string:
                        errors_found += [error_string]
                    continue
            #If all the above does not apply, this is a None value or plain text
            else:
                if new_human_value == 'None':
                    new_machine_value = None
                else:
                    new_machine_value = new_human_value

            #Try to translate the key to machine keys if possible
            try:
                original_machine_value = getattr(gloss,machine_key)
            except:
                error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(
                    gloss_id) + '), could not get original value for field: ' + str(machine_key)

                errors_found += [error_string]
                continue

            #Translate back the machine value from the gloss
            try:

                if hasattr(field, 'field_choice_category'):
                    # machine_key should be the same as field.name
                    original_machine_value = getattr(gloss, machine_key)
                    if original_machine_value:
                        original_machine_value = original_machine_value.machine_value
                    try:
                        # this is a bit confusing as to why a try is used instead of combining with the previous
                        original_human_value = getattr(gloss, field.name).name
                    except KeyError:
                        original_human_value = '-'
                        print('CSV Update: Original machine value for gloss ', gloss_id, ' has an undefined choice for field ', field.name, ': ', original_machine_value)
                        original_machine_value = None

                elif field.__class__.__name__ == 'BooleanField':
                    if original_machine_value is None and (field.name in settings.HANDEDNESS_ARTICULATION_FIELDS):
                        original_human_value = 'Neutral'
                    elif original_machine_value:
                        original_machine_value = True
                        original_human_value = 'True'
                    else:
                        original_machine_value = False
                        original_human_value = 'False'
                # some legacy glosses have empty text fields of other formats
                elif (field.__class__.__name__ == 'CharField' or field.__class__.__name__ == 'TextField') \
                        and (original_machine_value is None or original_machine_value == '-' or original_machine_value == '------' or original_machine_value == ' '):
                    original_machine_value = ''
                    original_human_value = ''
                else:
                    value = getattr(gloss, field.name)
                    original_human_value = value
            except:
                original_human_value = '-'
                error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(
                    gloss_id) + '), could not get choice for field '+field.verbose_name+': ' + str(original_machine_value)

                errors_found += [error_string]
                continue

            #Remove any weird char
            try:
                new_human_value = unescape(new_human_value)
            except:
                print('unescape raised exception for new_human_value: ', new_human_value)
                pass

            # test if blank value

            original_human_value = str(original_human_value)
            new_human_value = str(new_human_value)

            s1 = re.sub(' ','',original_human_value)
            s2 = re.sub(' ','',new_human_value)

            # If the original value is implicitly not set, and the new value is not set, ignore this change
            if (s1 == '' or s1 == 'None' or s1 == 'False') and s2 == '':
                pass
            #Check for change, and save your findings if there is one
            elif original_machine_value != new_machine_value and new_machine_value != None:
                if (human_key == 'WD' or human_key == 'WP') and original_human_value == 'None':
                    original_human_value = 'Neutral'
                differences.append({'pk':gloss_id,
                                    'dataset': current_dataset,
                                    'annotationidglosstranslation':default_annotationidglosstranslation,
                                    'machine_key':machine_key,
                                    'human_key':human_key,
                                    'original_machine_value':original_machine_value,
                                    'original_human_value':original_human_value,
                                    'new_machine_value':new_machine_value,
                                    'new_human_value':new_human_value})

    return (differences, errors_found, earlier_updates_same_csv, earlier_updates_lemmaidgloss)


def compare_valuedict_to_lemma(valuedict,lemma_id,my_datasets, nl,
                                lemmaidglosstranslations, current_lemmaidglosstranslations,
                               earlier_updates_same_csv, earlier_updates_lemmaidgloss):
    """Takes a dict of key-value pairs, and compares them to a lemma"""

    errors_found = []
    differences = []

    try:
        lemma = LemmaIdgloss.objects.select_related().get(pk=lemma_id)
    except ObjectDoesNotExist as e:

        e = 'Could not find lemma for ID ' + str(lemma_id)
        errors_found.append(e)
        return (differences, errors_found, earlier_updates_same_csv, earlier_updates_lemmaidgloss)

    if lemma_id in earlier_updates_same_csv:
        e = 'Lemma ID (' + str(lemma_id) + ') found in multiple rows (Row ' + str(nl + 1) + ').'
        errors_found.append(e)
        return (differences, errors_found, earlier_updates_same_csv, earlier_updates_lemmaidgloss)
    else:
        earlier_updates_same_csv.append(lemma_id)

    count_new_nonempty_translations = 0
    count_existing_nonempty_translations = 0

    if lemmaidglosstranslations \
            and current_lemmaidglosstranslations != lemmaidglosstranslations:
        for key1 in lemmaidglosstranslations.keys():
            if lemmaidglosstranslations[key1]:
                count_new_nonempty_translations += 1
        for key2 in current_lemmaidglosstranslations.keys():
            if current_lemmaidglosstranslations[key2]:
                count_existing_nonempty_translations += 1
        pass
    else:
        return (differences, errors_found, earlier_updates_same_csv, earlier_updates_lemmaidgloss)

    if not count_new_nonempty_translations:
        # somebody has modified the lemma translations so as to delete alll of them:
        e = 'Row ' + str(nl + 1) + ': Lemma ID ' + str(lemma_id) + ' must have at least one translation.'
        errors_found.append(e)
        return (differences, errors_found, earlier_updates_same_csv, earlier_updates_lemmaidgloss)


    #Create an overview of all fields, sorted by their human name
    with override(LANGUAGE_CODE):

        if lemma.dataset:
            current_dataset = lemma.dataset.acronym
        else:
            # because of legacy code, the current dataset might not have been set
            current_dataset = 'None'

        #Go through all values in the value dict, looking for differences with the lemma
        for human_key, new_human_value in valuedict.items():

            new_human_value = new_human_value.strip()

            if human_key == 'Lemma ID' or human_key == 'Dataset':
                # these fields can't be updated
                continue

            lemma_idgloss_key_prefix = "Lemma ID Gloss ("
            if human_key.startswith(lemma_idgloss_key_prefix):
                language_name_column = settings.DEFAULT_LANGUAGE_HEADER_COLUMN['English']
                language_name = human_key[len(lemma_idgloss_key_prefix):-1]
                languages = Language.objects.filter(**{language_name_column:language_name})
                if languages:
                    language = languages[0]
                    lemma_idglosses = lemma.lemmaidglosstranslation_set.filter(language=language)
                    if lemma_idglosses:
                        lemma_idgloss_string = lemma_idglosses[0].text
                    else:
                        # lemma not set
                        lemma_idgloss_string = ''
                    if lemma_idgloss_string != new_human_value:

                        differences.append({'pk': lemma_id,
                                            'dataset': current_dataset,
                                            'machine_key': human_key,
                                            'human_key': human_key,
                                            'original_machine_value': lemma_idgloss_string,
                                            'original_human_value': lemma_idgloss_string,
                                            'new_machine_value': new_human_value,
                                            'new_human_value': new_human_value})
                continue

            else:
                # this case should be impossible! It's included for completeness of else otherwise case
                print('Unknown lemma field encountered while comparing new to existing fields: ', human_key)

    return (differences, errors_found, earlier_updates_same_csv, earlier_updates_lemmaidgloss)


def check_existence_dialect(gloss, values):
    default_annotationidglosstranslation = get_default_annotationidglosstranslation(gloss)

    errors = []
    found = []
    not_found = []

    for new_value in values:
        if Dialect.objects.filter(name=new_value):
            if new_value in found:
                error_string = 'WARNING: For gloss ' + default_annotationidglosstranslation + ' (' + str(
                    gloss.pk) + '), new Dialect value ' + str(new_value) + ' is duplicate.'
                errors.append(error_string)
            else:
                found += [new_value]
        else:
            error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(gloss.pk) + '), new Dialect value ' + str(new_value) + ' not found.'
            errors.append(error_string)
            not_found += [new_value]
        continue

    return (found, not_found, errors)


def check_existance_signlanguage(gloss, values):
    default_annotationidglosstranslation = get_default_annotationidglosstranslation(gloss)

    errors = []
    found = []
    not_found = []

    for new_value in values:
        if SignLanguage.objects.filter(name=new_value):
            if new_value in found:
                error_string = 'WARNING: For gloss ' + default_annotationidglosstranslation + ' (' + str(
                    gloss.pk) + '), new Sign Language value ' + str(new_value) + ' is duplicate.'
                errors.append(error_string)
            else:
                found += [new_value]
        else:
            error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(gloss.pk) + '), new Sign Language value ' + str(new_value) + ' not found.'

            errors.append(error_string)
            not_found += [new_value]
        continue

    return (found, not_found, errors)

#See if there are any note typefield choices there, but don't crash if there isn't even a table
try:
    note_role_choices = list(FieldChoice.objects.filter(field__iexact='NoteType'))
except (OperationalError, ProgrammingError) as e:
    note_role_choices = []

all_notes = [ n.name for n in note_role_choices]

all_notes_display = ', '.join(all_notes)
# this is used to speedup matching updates to Notes
# it allows the type of note to be in either English or Dutch in the CSV file
note_reverse_translation = {}
for nrc in note_role_choices:
    note_reverse_translation[nrc.name] = nrc.machine_value

note_translations = {}
for nrc in note_role_choices:
    note_translations[str(nrc.machine_value)] = nrc.name

def check_existence_notes(gloss, values, note_type_error, note_tuple_error, default_annotationidglosstranslation):
    # convert new Notes csv value to proper format
    # values is not empty

    new_human_values = []
    new_note_errors = []

    split_human_values = re.findall(r'([^:]+:[^)]*\)),?\s?', values)

    for split_value in split_human_values:
        take_apart = re.match("([^:]+):\s?\((False|True),(\d),([^)]*)\)", split_value)
        if take_apart:
            (field, name, count, text) = take_apart.groups()

            if field not in all_notes:
                error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(
                    gloss.pk) + '), a non-existent note type was found: ' + field + '.'

                new_note_errors += [error_string]
                if not note_type_error:
                    error_string = 'Current note types are: ' + all_notes_display + '.'
                    new_note_errors += [error_string]
                    note_type_error = True
            else:
                new_tuple = (field, name, count, text)
                new_human_values.append(new_tuple)
        else:
            # error in processing new notes
            error_string = 'For ' + default_annotationidglosstranslation + ' (' + str(
                gloss.pk) + '), could not parse note: ' + split_value

            if not note_tuple_error:
                new_note_errors += [error_string]
                error_string1 = "Note values must be a comma-separated list of tagged tuples: 'Type:(Boolean,Index,Text)'"
                new_note_errors += [error_string1]
                error_string2 = 'Try exporting a CSV for glosses with Notes to check the format.'
                new_note_errors += [error_string2]
                note_tuple_error = True
            else:
                new_note_errors += [error_string]

    new_notes_display = [role + ':(' + published + ',' + count + ',' + text + ')' for (role, published, count, text) in
                         new_human_values]
    sorted_new_notes_list = sorted(new_notes_display)
    sorted_new_notes_display = ", ".join(sorted_new_notes_list)

    return (sorted_new_notes_display, new_note_errors, note_type_error, note_tuple_error)


def get_notes_as_string(gloss):
    activate(LANGUAGES[0][0])
    notes_of_gloss = gloss.definition_set.all()
    notes_list = []
    for note in notes_of_gloss:
        # use the notes field choice machine value rather than the translation
        note_field = note.role.name
        note_tuple = (note_field, str(note.published), str(note.count), note.text)
        notes_list.append(note_tuple)

    notes_display = [role + ':(' + published + ',' + count + ',' + text + ')' for (role, published, count, text) in
                     notes_list]
    sorted_notes_list = sorted(notes_display)
    sorted_notes_display = ', '.join(sorted_notes_list)

    return sorted_notes_display

def check_existance_sequential_morphology(gloss, values):
    default_annotationidglosstranslation = get_default_annotationidglosstranslation(gloss)

    errors = []
    found = []
    not_found = []

    for new_value in values:

        try:

            morpheme = Gloss.objects.get(pk=new_value)

            if new_value in found:
                error_string = 'WARNING: For gloss ' + default_annotationidglosstranslation + ' (' + str(
                    gloss.pk) + '), new Sequential Morphology value ' + str(new_value) + ' is duplicate.'
                errors.append(error_string)
            else:
                found += [new_value]

        # except ObjectDoesNotExist:
        except:
            if new_value in not_found:
                error_string = 'WARNING: For gloss ' + default_annotationidglosstranslation + ' (' + str(
                    gloss.pk) + '), new Sequential Morphology value ' + str(new_value) + ' is duplicate.'
            else:
                error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(
                    gloss.pk) + '), new Sequential Morphology value ' + str(new_value) + ' not found.'
            errors.append(error_string)
            not_found += [new_value]

            continue

    if len(values) > 4:
        error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(gloss.pk) + ', too many Sequential Morphology components.'
        errors.append(error_string)

    return (found, not_found, errors)

def check_existance_simultaneous_morphology(gloss, values):
    default_annotationidglosstranslation = get_default_annotationidglosstranslation(gloss)

    errors = []
    tuples_list = []
    checked = ''
    index_sim_morph = 0

    # check syntax
    for new_value_tuple in values:
        try:
            (morpheme, role) = new_value_tuple.split(':')
            role = role.strip()
            morpheme = morpheme.strip()
            tuples_list.append((morpheme,role))
        except ValueError:
            error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(gloss.pk) \
                           + '), formatting error in Simultaneous Morphology: ' + str(new_value_tuple) + '. Tuple morpheme:role expected.'
            errors.append(error_string)

    for (morpheme, role) in tuples_list:

        try:

            # get the id for the morpheme identifier
            # this is a gloss, make sure it exists
            morpheme_gloss = Gloss.objects.get(pk=morpheme)
            morpheme_id = Morpheme.objects.filter(gloss_ptr_id=morpheme_gloss)

            if not morpheme_id:
                error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(
                    gloss.pk) + '), new Simultaneous Morphology gloss ' + str(morpheme) + ' is not a morpheme.'
                errors.append(error_string)
                continue

            if checked:
                checked += ',' + ':'.join([morpheme, role])
            else:
                checked = ':'.join([morpheme, role])

        except ObjectDoesNotExist:
            error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(
                gloss.pk) + '), new Simultaneous Morphology value ' + str(morpheme) + ' is not a gloss.'
            errors.append(error_string)

            continue

    return (checked, errors)


def check_existance_blend_morphology(gloss, values):
    default_annotationidglosstranslation = get_default_annotationidglosstranslation(gloss)

    errors = []
    found = []
    not_found = []
    tuples_list = []
    checked = ''

    # check syntax
    for new_value_tuple in values:
        try:
            (gloss_id, role) = new_value_tuple.split(':')
            role = role.strip()
            gloss_id = gloss_id.strip()
            tuples_list.append((gloss_id,role))
        except ValueError:
            error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(gloss.pk) \
                           + '), formatting error in Blend Morphology: ' + str(new_value_tuple) + '. Tuple gloss:role expected.'
            errors.append(error_string)

    for (gloss_id, role) in tuples_list:

        try:

            morpheme_gloss = Gloss.objects.get(pk=gloss_id)

            if gloss_id in found:
                error_string = 'WARNING: For gloss ' + default_annotationidglosstranslation + ' (' + str(
                    gloss.pk) + '), new Blend Morphology value ' + str(gloss_id) + ' is duplicate.'
                errors.append(error_string)
            else:
                found += [gloss_id]

            if checked:
                checked += ',' + ':'.join([gloss_id, role])
            else:
                checked = ':'.join([gloss_id, role])

        except ObjectDoesNotExist:
            if gloss_id in not_found:
                # we've already seen this value
                error_string = 'WARNING: For gloss ' + default_annotationidglosstranslation + ' (' + str(
                    gloss.pk) + '), new Blend Morphology value ' + str(gloss_id) + ' is duplicate.'
                errors.append(error_string)
            else:
                error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(
                    gloss.pk) + '), new Blend Morphology value ' + str(gloss_id) + ' not found.'
                errors.append(error_string)
                not_found += [gloss_id]
            continue

    return (checked, errors)


RELATION_ROLES = ['homonym', 'Homonym', 'synonym', 'Synonym', 'variant', 'Variant', 'paradigm', 'Handshape Paradigm',
                         'antonym', 'Antonym', 'hyponym', 'Hyponym', 'hypernym', 'Hypernym', 'seealso', 'See Also']

RELATION_ROLES_DISPLAY = 'homonym, synonym, variant, paradigm, antonym, hyponym, hypernym, seealso'

def check_existance_relations(gloss, relations, values):
    default_annotationidglosstranslation = get_default_annotationidglosstranslation(gloss)

    errors = []
    checked = ''
    sorted_values = []

    # check syntax
    for new_value_tuple in values:
        try:
            (role, other_gloss) = new_value_tuple.split(':')
            role = role.strip()

            role = role.replace(' ', '')
            role = role.lower()
            other_gloss = other_gloss.strip()
            sorted_values.append((role,other_gloss))
        except ValueError:
            error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(gloss.pk) \
                           + '), formatting error in Relations to other signs: ' + str(new_value_tuple) + '. Tuple role:gloss expected.'
            errors.append(error_string)

    # remove duplicates
    sorted_values = list(set(sorted_values))

    sorted_values = sorted(sorted_values, key=lambda tup: tup[1])

    # check roles
    for (role, other_gloss) in sorted_values:

        try:
            if role not in RELATION_ROLES:
                raise ValueError
        except ValueError:
            error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(gloss.pk) \
                           + '), column Relations to other signs: ' + role + ':' + other_gloss + '. Role ' + role + ' not found.' \
                    + ' Role should be one of: ' + RELATION_ROLES_DISPLAY + '.'
            errors.append(error_string)

    # check other glosses
    for (role, other_gloss) in sorted_values:

        try:

            target_gloss = Gloss.objects.get(pk=other_gloss)

            if not target_gloss:
                raise ObjectDoesNotExist

            if checked:
                checked += ',' + ':'.join([role, other_gloss])
            else:
                checked = ':'.join([role, other_gloss])

        except ObjectDoesNotExist:
            error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(gloss.pk) \
                    + '), column Relations to other signs: ' + role + ':' + other_gloss + '. Other gloss ' + other_gloss + ' not found.' \
                    + ' Please use Annotation ID Gloss: Dutch to identify the other gloss.'
            errors.append(error_string)

            pass

    return (checked, errors)


def check_existance_foreign_relations(gloss, relations, values):
    default_annotationidglosstranslation = get_default_annotationidglosstranslation(gloss)

    errors = []
    checked = ''
    sorted_values = []

    for new_value_tuple in values:
        try:
            (loan_word, other_lang, other_lang_gloss) = new_value_tuple.split(':')
            sorted_values.append((loan_word,other_lang,other_lang_gloss))
        except ValueError:
            error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(gloss.pk) \
                           + '), formatting error in Relations to foreign signs: ' + str(new_value_tuple) + '. Tuple bool:string:string expected.'
            errors.append(error_string)

    # remove duplicates
    sorted_values = list(set(sorted_values))

    sorted_values = sorted(sorted_values, key=lambda tup: tup[2])

    for (loan_word, other_lang, other_lang_gloss) in sorted_values:

        # check the syntax of the tuple of changes
        try:
            loan_word = loan_word.strip()
            if loan_word not in ['false', 'False', 'true', 'True']:
                raise ValueError
            other_lang = other_lang.strip()
            other_lang_gloss = other_lang_gloss.strip()
            if checked:
                checked += ',' + ':'.join([loan_word, other_lang, other_lang_gloss])
            else:
                checked = ':'.join([loan_word,other_lang,other_lang_gloss])
        except ValueError:
            error_string = 'ERROR: For gloss ' + default_annotationidglosstranslation + ' (' + str(gloss.pk) \
                           + '), formatting error in Relations to foreign signs: ' \
                           + loan_word + ':' + other_lang + ':' + other_lang_gloss + '. Tuple bool:string:string expected.'
            errors.append(error_string)

            pass

    return (checked, errors)

def reload_signbank(request=None):
    """Functions to clear the cache of Apache, also works as view"""

    #Refresh the wsgi script
    os.utime(WSGI_FILE,None)

    #If this is an HTTP request, give an HTTP response
    if request != None:

        from django.shortcuts import render
        return render(request,'reload_signbank.html')

def get_gloss_data(since_timestamp=0, dataset=None):
    if dataset:
        glosses = Gloss.objects.filter(lemma__dataset=dataset)
    else:
        glosses = Gloss.objects.all()
    gloss_data = {}
    for gloss in glosses:
        if int(format(gloss.lastUpdated, 'U')) > since_timestamp:
            gloss_data[gloss.pk] = gloss.get_fields_dict()

    return gloss_data

def create_zip_with_json_files(data_per_file,output_path):

    """Creates a zip file filled with the output of the functions supplied.

    Data should either be a json string or a list, which will be transformed to json."""

    INDENTATION_CHARS = 4

    zip = ZipFile(output_path,'w')

    for filename, data in data_per_file.items():

        if isinstance(data,list) or isinstance(data,dict):
            output = json.dumps(data,indent=INDENTATION_CHARS)
            zip.writestr(filename+'.json',output)

def get_deleted_gloss_or_media_data(item_type,since_timestamp):

    result = []
    from datetime import datetime, date
    deletion_date_range = [datetime.fromtimestamp(since_timestamp),date.today()]

    for deleted_gloss_or_media in DeletedGlossOrMedia.objects.filter(deletion_date__range=deletion_date_range,
                                                            item_type=item_type):
        if item_type == 'gloss':
            result.append((str(deleted_gloss_or_media.old_pk), deleted_gloss_or_media.idgloss))
        else:
            result.append(str(deleted_gloss_or_media.old_pk))

    return result


def generate_still_image(video):
    try:
        from CNGT_scripts.python.extractMiddleFrame import MiddleFrameExtracter
        # local copy for debugging purposes
        # from signbank.video.extractMiddleFrame import MiddleFrameExtracter
        from signbank.settings.server_specific import FFMPEG_PROGRAM, TMP_DIR
        from signbank.settings.base import GLOSS_IMAGE_DIRECTORY

        # Extract frames (incl. middle)
        extracter = MiddleFrameExtracter([os.path.join(WRITABLE_FOLDER, str(video.videofile))],
                                         os.path.join(TMP_DIR, "signbank-ExtractMiddleFrame"), FFMPEG_PROGRAM, True)
        output_dirs = extracter.run()

        # Copy video still to the correct location
        vfile_name = os.path.basename(str(video.videofile))
        still_goal_location = os.path.join(WRITABLE_FOLDER,
                                           str(video.videofile).replace(GLOSS_VIDEO_DIRECTORY, GLOSS_IMAGE_DIRECTORY, 1))
        destination = os.path.dirname(still_goal_location)
        for dir in output_dirs:
            for filename in os.listdir(dir):
                if filename.replace('.png', '') == os.path.splitext(vfile_name)[0]:
                    if not os.path.isdir(destination):
                        os.makedirs(destination, 0o770)
                    shutil.copy(os.path.join(dir, filename), destination)
            shutil.rmtree(dir)
        print("Generating still images succes!")
    except ImportError as i:
        print("Error resizing video: ", i)
    except IOError as io:
        print("IOError: ", io)


def get_datasets_with_public_glosses():

    # Make sure a non-empty set is returned, for anonymous users when no datasets are public
    # the first query fetches glosses that are public, then obtains those glosses' dataset ids
    datasets_of_public_glosses = Gloss.objects.filter(inWeb=True).values('lemma__dataset__id').distinct()
    datasets_with_public_glosses = Dataset.objects.filter(id__in=datasets_of_public_glosses)
    return datasets_with_public_glosses


def get_selected_datasets_for_user(user, readonly=False):
    if user.is_authenticated:
        user_profile = UserProfile.objects.get(user=user)
        viewable_datasets = get_objects_for_user(user, 'can_view_dataset', Dataset)
        selected_datasets = user_profile.selected_datasets.all()
        if not selected_datasets:
            return viewable_datasets
        return selected_datasets & viewable_datasets # intersection of the selected and viewable datasets
    elif readonly:
        selected_datasets = Dataset.objects.all()
        return selected_datasets
    else:
        # Make sure a non-empty set is returned, for anonymous users when no datasets are public
        selected_datasets = Dataset.objects.filter(acronym=settings.DEFAULT_DATASET_ACRONYM)
        return selected_datasets


def get_dataset_languages(datasets):
    """
    Return Language queryset containing languages for given datasets
    :param datasets: 
    :return: dataset_languages: Language queryset: 
    """
    try:
        dataset_languages = Language.objects.filter(dataset__in=datasets).distinct()
    except EmptyResultSet:
        dataset_languages = Language.objects.none()
    return dataset_languages


def get_users_without_dataset():

    users_with_no_dataset = []

    for user in User.objects.all():
        if user.is_active and len(get_objects_for_user(user, 'can_view_dataset', Dataset)) == 0:
            users_with_no_dataset.append(user)

    return users_with_no_dataset

def gloss_from_identifier(value):
    """Given an id of the form "idgloss (pk)" return the
    relevant gloss or None if none is found
    BUT: first check if a unique hit can be found by the string alone (if it is not empty)
    """

    match = re.match('(.*) \((\d+)\)', value)
    if match:
        print("MATCH: ", match)
        annotation_idgloss = match.group(1)
        pk = match.group(2)
        print("INFO: ", annotation_idgloss, pk)

        target = Gloss.objects.get(pk=int(pk))
        print("TARGET: ", target)
        return target
    elif value != '':
        annotation_idgloss = value
        target = Gloss.objects.get(annotation_idgloss=annotation_idgloss)
        return target
    else:
        return None

def get_default_annotationidglosstranslation(gloss):
    default_annotationidglosstranslation = ""
    language = Language.objects.get(**DEFAULT_KEYWORDS_LANGUAGE)
    annotationidglosstranslations = gloss.annotationidglosstranslation_set.filter(language=language)
    if annotationidglosstranslations and len(annotationidglosstranslations) > 0:
        default_annotationidglosstranslation = annotationidglosstranslations[0].text
    return default_annotationidglosstranslation


from signbank.settings.base import ECV_FILE,EARLIEST_GLOSS_CREATION_DATE, FIELDS, SEPARATE_ENGLISH_IDGLOSS_FIELD, LANGUAGE_CODE, ECV_SETTINGS, URL, LANGUAGE_CODE_MAP
from signbank.settings import server_specific
from signbank.settings.server_specific import *
import re
import datetime as DT


def gloss_handshape_fields():
    # returns a list of fields that are Handshape ForeignKeys
    fields_list = []

    from signbank.dictionary.models import Gloss
    for gloss_field in Gloss._meta.fields:
        if isinstance(gloss_field, models.ForeignKey) and gloss_field.related_model == Handshape:
            fields_list.append(gloss_field.name)
    return fields_list


def fields_with_choices_glosses():
    # return a dict that maps the field choice categories to the fields of Gloss that have the category

    fields_dict = {}

    from signbank.dictionary.models import Gloss
    for field in Gloss._meta.fields:
        if hasattr(field, 'field_choice_category') and isinstance(field, FieldChoiceForeignKey):
            # field has choices
            field_category = field.field_choice_category
            if field_category in fields_dict.keys():
                fields_dict[field_category].append(field.name)
            else:
                fields_dict[field_category] = [field.name]
    return fields_dict

def fields_with_choices_handshapes():
    # return a dict that maps the field choice categories to the fields of Handshape that have the category

    fields_dict = {}

    from signbank.dictionary.models import Handshape
    for field in Handshape._meta.fields:
        if hasattr(field, 'field_choice_category') and isinstance(field, FieldChoiceForeignKey):
            # field has choices
            field_category = field.field_choice_category
            if field_category in fields_dict.keys():
                fields_dict[field_category].append(field.name)
            else:
                fields_dict[field_category] = [field.name]
    return fields_dict

def fields_with_choices_definition():
    # return a dict that maps the field choice categories to the fields of Definition that have the category

    fields_dict = {}

    from signbank.dictionary.models import Definition
    for field in Definition._meta.fields:
        if hasattr(field, 'field_choice_category') and isinstance(field, FieldChoiceForeignKey):
            # field has choices
            field_category = field.field_choice_category
            if field_category in fields_dict.keys():
                fields_dict[field_category].append(field.name)
            else:
                fields_dict[field_category] = [field.name]
    return fields_dict

def fields_with_choices_morphology_definition():
    # return a dict that maps the field choice categories to the fields of MorphologyDefinition that have the category

    fields_dict = {}

    from signbank.dictionary.models import MorphologyDefinition
    for field in MorphologyDefinition._meta.fields:
        if hasattr(field, 'field_choice_category') and isinstance(field, FieldChoiceForeignKey):
            # field has choices
            field_category = field.field_choice_category
            if field_category in fields_dict.keys():
                fields_dict[field_category].append(field.name)
            else:
                fields_dict[field_category] = [field.name]
    return fields_dict

def fields_with_choices_other_media_type():
    # return a dict that maps the field choice categories to the fields of OtherMediaType that have the category

    fields_dict = {}

    from signbank.dictionary.models import OtherMedia
    for field in OtherMedia._meta.fields:
        if hasattr(field, 'field_choice_category') and isinstance(field, FieldChoiceForeignKey):
            # field has choices
            field_category = field.field_choice_category
            if field_category in fields_dict.keys():
                fields_dict[field_category].append(field.name)
            else:
                fields_dict[field_category] = [field.name]
    return fields_dict

def fields_with_choices_morpheme_type():
    # return a dict that maps the field choice categories to the fields of MorphemeType that have the category

    fields_dict = {}

    from signbank.dictionary.models import Morpheme
    for field in Morpheme._meta.fields:
        if field in Gloss._meta.fields:
            # skip fields that are also in superclass Gloss
            continue
        if hasattr(field, 'field_choice_category') and isinstance(field, FieldChoiceForeignKey):
            # field has choices
            field_category = field.field_choice_category
            if field_category in fields_dict.keys():
                fields_dict[field_category].append(field.name)
            else:
                fields_dict[field_category] = [field.name]
    return fields_dict

def write_ecv_files_for_all_datasets():

    all_dataset_objects = Dataset.objects.all()

    for ds in all_dataset_objects:
        ecv_filename = write_ecv_file_for_dataset(ds.acronym)
        print('Saved ECV for Dataset ', ds.name, ' to file: ', ecv_filename)

    return True


def write_ecv_file_for_dataset(dataset_name):
    dataset_id = Dataset.objects.get(acronym=dataset_name)

    query_dataset = Gloss.none_morpheme_objects().filter(excludeFromEcv=False).filter(lemma__dataset=dataset_id)
    if not query_dataset:
        return ''

    sOrder = 'annotationidglosstranslation__text'
    if dataset_id.default_language:
        lang_attr_name = dataset_id.default_language.language_code_2char
    else:
        lang_attr_name = settings.DEFAULT_KEYWORDS_LANGUAGE['language_code_2char']
    sort_language = 'annotationidglosstranslation__language__language_code_2char'
    qs_empty = query_dataset.filter(**{sOrder + '__isnull': True})
    qs_letters = query_dataset.filter(**{sOrder + '__regex': r'^[a-zA-Z]', sort_language: lang_attr_name})
    qs_special = query_dataset.filter(**{sOrder + '__regex': r'^[^a-zA-Z]', sort_language: lang_attr_name})

    ordered = list(qs_letters.order_by(sOrder))
    ordered += list(qs_special.order_by(sOrder))
    ordered += list(qs_empty)

    context = {
        'CV_ID': ECV_SETTINGS['CV_ID'] if 'CV_ID' in ECV_SETTINGS else "",
        'date': str(DT.date.today()) + 'T' + str(DT.datetime.now().time()),
        'glosses': ordered,
        'dataset': dataset_id,
        'languages': dataset_id.translation_languages.all(),
        'resource_url': URL + PREFIX_URL + '/dictionary/gloss/'
    }
    from django.template.loader import get_template
    ecv_template = get_template('dictionary/ecv.xml')
    xmlstr = ecv_template.render(context)
    ecv_file = os.path.join(ECV_FOLDER, dataset_name.lower().replace(" ","_") + ".ecv")
    import codecs
    with codecs.open(ecv_file, "w", "utf-8") as f:
        f.write(xmlstr)

    return ecv_file

def get_ecv_description_for_gloss(gloss, lang, include_phonology_and_frequencies=False):
    activate(lang)

    desc = ""
    if include_phonology_and_frequencies:

        for f in ECV_SETTINGS['description_fields']:
            gloss_field = getattr(gloss, f)
            if isinstance(gloss_field, FieldChoice) or isinstance(gloss_field, Handshape):
                value = getattr(gloss, f).name
            else:
                value = get_value_for_ecv(gloss, f)

            # potential error: this pretty printing assumes a particular ordering of the fields
            # parens might not match if sorted otherwise
            # these fields seem to be hard coded
            if f == 'handedness':
                desc = value
            elif f == 'domhndsh':
                desc = desc + ', (' + value
            elif f == 'subhndsh':
                desc = desc + ',' + value
            elif f == 'handCh':
                desc = desc + '; ' + value + ')'
            elif f == 'tokNo':
                desc = desc + ' [' + value
            elif f == 'tokNoSgnr':
                desc = desc + '/' + value + ']'
            else:
                desc = desc + ', ' + value

    if desc:
        desc += ", "

    trans = [t.translation.text for t in gloss.translation_set.all()]
    desc += ", ".join(
        # The next line was adapted from an older version of this code,
        # that happened to do nothing. I left this for future usage.
        # map(lambda t: str(t.encode('ascii','xmlcharrefreplace')) if isinstance(t, unicode) else t, trans)
        trans
    )

    return desc

def get_value_for_ecv(gloss, fieldname):
    value = None
    annotationidglosstranslation_prefix = "annotationidglosstranslation_"
    if fieldname.startswith(annotationidglosstranslation_prefix):
        language_code_2char = fieldname[len(annotationidglosstranslation_prefix):]
        annotationidglosstranslations = gloss.annotationidglosstranslation_set.filter(
            language__language_code_2char=language_code_2char)
        if annotationidglosstranslations and len(annotationidglosstranslations) > 0:
            value = annotationidglosstranslations[0].text
    else:
        try:
            value = getattr(gloss, 'get_' + fieldname + '_display')()

        except AttributeError:
            value = getattr(gloss, fieldname)

    # This was disabled with the move to python 3... might not be needed anymore
    # if isinstance(value,unicode):
    #     value = str(value.encode('ascii','xmlcharrefreplace'))

    if value is None:
        value = " "
    elif not isinstance(value, str):
        value = str(value)

    if value == '-':
        value = ' '
    return value

def write_csv_for_handshapes(handshapelistview, csvwriter):
#  called from the HandshapeListView when search_type is handshape

    fields = [Handshape._meta.get_field(fieldname) for fieldname in settings.HANDSHAPE_RESULT_FIELDS]

    activate(LANGUAGES[0][0])
    header = ['Handshape ID'] + [ f.verbose_name.encode('ascii', 'ignore').decode() for f in fields ]

    csvwriter.writerow(header)

    # case search result is list of handshapes

    handshape_list = handshapelistview.object_list

    for handshape in handshape_list:
        row = [str(handshape.pk)]

        for f in fields:
            # Try the value of the choicelist
            if hasattr(f, 'field_choice_category'):
                if hasattr(handshape, 'get_' + f.name + '_display'):
                    value = getattr(handshape, 'get_' + f.name + '_display')()
                else:
                    value = getattr(handshape, f.name)
                    if value is not None:
                        value = value.name
            else:
                value = getattr(handshape, f.name)

            if not isinstance(value, str):
                value = str(value)

            if value is None:
                if f.__class__.__name__ == 'CharField' or f.__class__.__name__ == 'TextField':
                    value = ''
                elif f.__class__.__name__ == 'IntegerField':
                    value = 0
                else:
                    value = ''

            row.append(value)

        # Make it safe for weird chars
        safe_row = []
        for column in row:
            try:
                safe_row.append(column.encode('utf-8').decode())
            except AttributeError:
                safe_row.append(None)

        csvwriter.writerow(safe_row)

    return csvwriter


def get_users_who_can_view_dataset(dataset_name):

    dataset = Dataset.objects.get(acronym=dataset_name)

    all_users = User.objects.all()

    users_who_can_view_dataset = []

    for user in all_users:
        import guardian
        from guardian.shortcuts import get_objects_for_user
        user_view_datasets = guardian.shortcuts.get_objects_for_user(user, 'can_view_dataset', Dataset)
        if dataset in user_view_datasets:
            users_who_can_view_dataset.append(user.username)

    return users_who_can_view_dataset


def construct_scrollbar(qs, search_type, language_code):
    items = []
    if search_type in ['sign', 'sign_or_morpheme', 'morpheme', 'sign_handshape']:
        for item in qs:
            if item.is_morpheme():
                item_is_morpheme = 'morpheme'
            else:
                item_is_morpheme = 'gloss'
            annotationidglosstranslations = item.annotationidglosstranslation_set.filter(
                language__language_code_2char__exact=language_code
            )
            if annotationidglosstranslations and len(annotationidglosstranslations) > 0:
                gloss_text = annotationidglosstranslations[0].text
                if not gloss_text:
                    gloss_text = item.idgloss
                items.append(dict(id=item.id, data_label=gloss_text, href_type=item_is_morpheme))
            else:
                # no annotations found for gloss
                # idgloss defaults to the id if nothing is found
                items.append(dict(id=item.id, data_label=item.idgloss, href_type=item_is_morpheme))

    elif search_type in ['handshape']:
        for item in qs:
            data_label = item.name
            items.append(dict(id = item.machine_value, data_label = data_label, href_type = 'handshape'))
    elif search_type in ['lemma']:
        # there is no lemma detail view, so the href goes to lemma/update
        for item in qs:
            lemmaidglosstranslations = item.lemmaidglosstranslation_set.all()
            if lemmaidglosstranslations:
                if len(lemmaidglosstranslations) == 1:
                    # there are lemma's with only one translation, make sure they can be printed in the scroll bar
                    lemma_text = lemmaidglosstranslations[0].text
                else:
                    lemma_text = str(item.id)
                    for tr in lemmaidglosstranslations:
                        if tr.language.language_code_2char == language_code:
                            lemma_text = tr.text
                items.append(dict(id=item.id, data_label=lemma_text, href_type='lemma/update'))
            else:
                # no translations found for lemma
                items.append(dict(id=item.id, data_label=str(item.id), href_type='lemma/update'))

    return items

def write_csv_for_minimalpairs(minimalpairslistview, language_code):
#  called from the MinimalPairsListView

    rows = []

    minimalpairs_list = minimalpairslistview.get_queryset()
    # for debug purposes use a count, otherwise this is extremely slow if all glosses are shown
    for glo in minimalpairs_list:
        if hasattr(settings, 'SHOW_DATASET_INTERFACE_OPTIONS') and settings.SHOW_DATASET_INTERFACE_OPTIONS:
            try:
                mp_dataset = glo.lemma.dataset.acronym
            except:
                mp_dataset = 'None'
            focus_gloss_columns = [ mp_dataset]
        else:
            focus_gloss_columns = []

        translation_focus_gloss = ""
        translations_gloss = glo.annotationidglosstranslation_set.filter(
            language__language_code_2char=language_code)
        if translations_gloss and len(translations_gloss) > 0:
            translation_focus_gloss = translations_gloss[0].text

        focus_gloss_columns.append(translation_focus_gloss)
        focus_gloss_columns.append(str(glo.pk))

        minimal_pairs = minimalpairs_focusgloss(glo.pk, language_code)

        if minimal_pairs:
            for mpd in minimal_pairs:
                other_gloss_columns = []
                other_gloss_columns.append(mpd['other_gloss_idgloss'])
                other_gloss_columns.append(mpd['id'])
                other_gloss_columns.append(mpd['field_display'])
                other_gloss_columns.append(mpd['focus_gloss_value'])
                other_gloss_columns.append(mpd['other_gloss_value'])

                # Make it safe for weird chars
                safe_row = []
                for column in focus_gloss_columns + other_gloss_columns:
                    try:
                        safe_row.append(column.encode('utf-8').decode())
                    except AttributeError:
                        safe_row.append(None)

                rows.append(safe_row)
        else:
            # Make it safe for weird chars
            safe_row = []
            for column in focus_gloss_columns:
                try:
                    safe_row.append(column.encode('utf-8').decode())
                except AttributeError:
                    safe_row.append(None)

            rows.append(safe_row)

    return rows

def minimalpairs_focusgloss(gloss_id, language_code):

    from django.utils import translation
    translation.activate(language_code)

    this_gloss = Gloss.objects.get(id=gloss_id)

    try:
        minimalpairs_objects = this_gloss.minimal_pairs_dict()
    except:
        minimalpairs_objects = {}

    result = []
    for minimalpairs_object, minimal_pairs_dict in minimalpairs_objects.items():

        other_gloss_dict = dict()
        other_gloss_dict['id'] = str(minimalpairs_object.id)
        other_gloss_dict['other_gloss'] = minimalpairs_object
        for field, values in minimal_pairs_dict.items():

            other_gloss_dict['field'] = field
            other_gloss_dict['field_display'] = values[0]
            other_gloss_dict['field_category'] = values[1]

            focus_gloss_choice = values[2]
            other_gloss_choice = values[3]

            if focus_gloss_choice:
                pass
            else:
                focus_gloss_choice = ''
            if other_gloss_choice:
                pass
            else:
                other_gloss_choice = ''

            field_kind = values[4]
            if field_kind == 'list':
                focus_gloss_value = focus_gloss_choice
            elif field_kind == 'check':
                # the value is a Boolean or it might not be set
                if focus_gloss_choice == 'True' or focus_gloss_choice == True:
                    focus_gloss_value = 'Yes'
                elif focus_gloss_choice == 'Neutral' and field in settings.HANDEDNESS_ARTICULATION_FIELDS:
                    focus_gloss_value = 'Neutral'
                else:
                    focus_gloss_value = 'No'
            else:
                # translate Boolean fields
                focus_gloss_value = focus_gloss_choice
            other_gloss_dict['focus_gloss_value'] = focus_gloss_value
            if field_kind == 'list':
                other_gloss_value = other_gloss_choice
            elif field_kind == 'check':
                # the value is a Boolean or it might not be set
                if other_gloss_choice == 'True' or other_gloss_choice == True:
                    other_gloss_value = 'Yes'
                elif other_gloss_choice == 'Neutral' and field in settings.HANDEDNESS_ARTICULATION_FIELDS:
                    other_gloss_value = 'Neutral'
                else:
                    other_gloss_value = 'No'
            else:
                other_gloss_value = other_gloss_choice
            other_gloss_dict['other_gloss_value'] = other_gloss_value
            other_gloss_dict['field_kind'] = field_kind

        translation = ""
        translations = minimalpairs_object.annotationidglosstranslation_set.filter(language__language_code_2char=language_code)
        if translations is not None and len(translations) > 0:
            translation = translations[0].text
        else:
            translations = minimalpairs_object.annotationidglosstranslation_set.filter(language__language_code_3char='eng')
            if translations is not None and len(translations) > 0:
                translation = translations[0].text

        other_gloss_dict['other_gloss_idgloss'] = translation
        result.append(other_gloss_dict)
    return result

def strip_control_characters(input):

    if input:

        import re

        # remove an ending backslash
        input = re.sub(r"\\$", "", input)

    return input

def searchform_panels(searchform, searchfields) :
    search_by_fields = []
    for field in searchfields:
        form_field_parameters = (field,searchform.fields[field].label,searchform[field])
        search_by_fields.append(form_field_parameters)
    return search_by_fields

def map_search_results_to_gloss_list(search_results):

    if not search_results:
        return ([], [])
    gloss_ids = []
    for search_result in search_results:
        gloss_ids.append(search_result['id'])
    return (gloss_ids, Gloss.objects.filter(id__in=gloss_ids))



def get_interface_language_and_default_language_codes(request):
    default_language = Language.objects.get(id=get_default_language_id())
    default_language_code = default_language.language_code_2char
    interface_language_3char = dict(settings.LANGUAGES_LANGUAGE_CODE_3CHAR)[request.LANGUAGE_CODE]
    interface_language = Language.objects.get(language_code_3char=interface_language_3char)
    interface_language_code = interface_language.language_code_2char

    return (interface_language, interface_language_code, default_language, default_language_code)
