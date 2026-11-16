"""Spec: data-links (change data-links, #670, epic #676).

A dataset is linked into surveys and Site map blocks, not copied; links are guarded; every place
that uses a dataset is listed, before a delete too; linked layers keep the memory rules.
"""
import json

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_pro_org, make_v1_survey
from data.datasets import sync
from data.models import Dataset, DatasetLink
from survey.layers import layers_for, rebuild_layer
from survey.models import LayerObject, Question, Site, SiteBlock, SurveyMapLayer


class _LinkFixture(TestCase):
    """A workspace dataset "Street trees" (two trees, public, documented) and two published surveys."""

    def setUp(self):
        self.org, self.owner = make_pro_org('LinkOrg', 'linkowner')
        self.survey_a, self.section_a = make_v1_survey(self.org, self.owner, name='Survey A', status='published')
        self.survey_b, _sec = make_v1_survey(self.org, self.owner, name='Survey B', status='published')
        self.layer = SurveyMapLayer.objects.create(survey=None, organization=self.org, name='Street trees', geojson='')
        for i, species in enumerate(['Lime', 'Oak']):
            LayerObject.objects.create(layer=self.layer, key=f't{i}', title=f'Tree {i}', position=i,
                                       geometry=Point(-0.1234 + i / 1000, 51.5678),
                                       properties={'species': species, 'height': 10 + i})
        sync(self.org)
        self.dataset = Dataset.objects.get(layer=self.layer)
        self.dataset.privacy_class = Dataset.PRIVACY_PUBLIC
        self.dataset.fields = [{'name': 'species', 'label': 'Species', 'type': 'text', 'private': False},
                               {'name': 'height', 'label': 'Height (m)', 'type': 'number', 'private': False}]
        self.dataset.save()
        rebuild_layer(self.layer)
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def link(self, survey, dataset=None):
        return self.client.post(reverse('editor_survey_layer_link', args=[survey.uuid]),
                                {'dataset': (dataset or self.dataset).pk})

    def layer_geojson(self, survey):
        url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(survey.uuid), 'layer_id': self.layer.pk})
        return self.client.get(url)

    def site_with_block(self):
        site = Site.objects.create(organization=self.org, title='Park plan', slug='park-plan',
                                   created_by=self.owner, is_published=True)
        r = self.client.post(reverse('editor_site_block_add', args=[site.uuid]),
                             {'kind': 'map', 'dataset': str(self.dataset.pk)})
        self.assertEqual(r.status_code, 302, r.content[:500])
        return site, site.blocks.get(kind='map')


class LinkTest(_LinkFixture):
    """Requirement: A dataset is linked into surveys and sites, not copied."""

    def test_one_dataset_in_two_surveys_and_a_site(self):
        """
        GIVEN a dataset linked into two surveys and a Site map block
        WHEN one of its objects is renamed
        THEN both surveys' layer GeoJSON and the Site block's GeoJSON carry the new name
        """
        self.assertEqual(self.link(self.survey_a).status_code, 201)
        self.assertEqual(self.link(self.survey_b).status_code, 201)
        site, block = self.site_with_block()
        self.assertEqual(SurveyMapLayer.objects.count(), 1)   # nothing was copied
        obj = LayerObject.objects.get(layer=self.layer, key='t0')
        obj.title = 'Renamed lime'
        obj.save()
        rebuild_layer(self.layer)
        self.client.logout()   # respondents and visitors
        for survey in (self.survey_a, self.survey_b):
            self.assertIn('Renamed lime', self.layer_geojson(survey).content.decode())
        body = self.client.get(reverse('site_block_dataset', args=[site.slug, block.pk])).content.decode()
        self.assertIn('Renamed lime', body)
        self.assertEqual(self.dataset.links.count(), 3)

    def test_card_fields_per_link(self):
        """
        GIVEN survey A shows only `species` for its link
        WHEN a respondent opens an object's card on survey A
        THEN the card lists Species and not Height (m)
        """
        link_id = self.link(self.survey_a).json()['id']
        self.client.post(reverse('editor_survey_layer_link_fields', args=[self.survey_a.uuid, link_id]),
                         {'fields': ['species']})
        self.client.logout()
        url = reverse('survey_layer_object', kwargs={'survey_slug': str(self.survey_a.uuid),
                                                     'layer_id': self.layer.pk, 'key': 't0'})
        labels = [f['label'] for f in self.client.get(url).json()['fields']]
        self.assertEqual(labels, ['Species'])

    def test_linked_layer_cannot_be_edited_from_the_survey(self):
        """
        GIVEN survey A links the dataset
        WHEN its owner posts a settings change for that layer
        THEN the request is refused and the layer keeps its name
        """
        self.link(self.survey_a)
        r = self.client.post(reverse('editor_survey_layer_update', args=[self.survey_a.uuid, self.layer.pk]),
                             {'name': 'Hijacked'})
        self.assertEqual(r.status_code, 404)
        self.layer.refresh_from_db()
        self.assertEqual(self.layer.name, 'Street trees')

    def test_duplicate_survey_keeps_the_link(self):
        """
        GIVEN survey A links the dataset
        WHEN survey A is duplicated
        THEN the copy links the same dataset and copies no layer
        """
        from survey.cloning import clone_survey
        self.link(self.survey_a)
        copy = clone_survey(self.survey_a, created_by=self.owner)
        self.assertEqual(list(layers_for(copy).values_list('pk', flat=True)), [self.layer.pk])
        self.assertEqual(SurveyMapLayer.objects.count(), 1)


class GuardTest(_LinkFixture):
    """Requirement: Links are guarded."""

    def test_private_dataset_is_refused(self):
        """
        GIVEN the dataset is private
        WHEN the owner links it into a survey and into a Site map block
        THEN both are refused with a message to make it public first
        """
        Dataset.objects.filter(pk=self.dataset.pk).update(privacy_class=Dataset.PRIVACY_PRIVATE)
        r = self.link(self.survey_a)
        self.assertEqual(r.status_code, 400)
        self.assertIn('public', r.json()['error'])
        site = Site.objects.create(organization=self.org, title='S', slug='s-site', created_by=self.owner)
        self.client.post(reverse('editor_site_block_add', args=[site.uuid]), {'kind': 'map', 'dataset': str(self.dataset.pk)})
        self.assertFalse(SiteBlock.objects.filter(site=site, kind='map', data__dataset=self.dataset.pk).exists())
        self.assertFalse(DatasetLink.objects.exists())

    def test_linked_dataset_cannot_be_made_private(self):
        """
        GIVEN the dataset is linked into survey A
        WHEN the owner sets it to private on its page
        THEN it stays public and the page names survey A
        """
        self.link(self.survey_a)
        page = reverse('editor_data_dataset', args=[self.dataset.pk])
        r = self.client.post(page, {'action': 'privacy', 'privacy_class': 'private'}, follow=True)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.privacy_class, 'public')
        self.assertIn('Survey A', r.content.decode())

    def test_above_the_caps_is_refused(self):
        """
        GIVEN a dataset of 6,000 objects
        WHEN the owner links it into a survey
        THEN the link is refused naming the 5,000-object limit
        """
        SurveyMapLayer.objects.filter(pk=self.layer.pk).update(feature_count=6000)
        r = self.link(self.survey_a)
        self.assertEqual(r.status_code, 400)
        self.assertIn('5000', r.json()['error'].replace(',', ''))

    def test_unlinking_a_bound_dataset_is_refused(self):
        """
        GIVEN an Objects-on-the-map question of survey A is bound to the linked layer
        WHEN the owner unlinks the dataset
        THEN the unlink is refused naming the question
        """
        link_id = self.link(self.survey_a).json()['id']
        Question.objects.create(survey_section=self.section_a, code='OBJ', name='Rate the trees',
                                input_type='layer_objects', layer=self.layer)
        r = self.client.post(reverse('editor_survey_layer_unlink', args=[self.survey_a.uuid, link_id]))
        self.assertEqual(r.status_code, 400)
        self.assertIn('Rate the trees', r.json()['error'])
        self.assertTrue(DatasetLink.objects.filter(pk=link_id).exists())


class UsedByTest(_LinkFixture):
    """Requirement: Every place that uses a dataset is listed."""

    def test_delete_page_lists_the_places(self):
        """
        GIVEN the dataset is linked into survey A and a Site
        WHEN the owner opens its delete page
        THEN the page names survey A and the site before the confirm button
        """
        self.link(self.survey_a)
        self.site_with_block()
        html = self.client.get(reverse('editor_data_delete', args=[self.dataset.pk])).content.decode()
        listed = html.split('data-testid="delete-used-by"')[1].split('</ul>')[0]
        self.assertIn('Survey A', listed)
        self.assertIn('Park plan', listed)
        self.assertLess(html.index('Park plan'), html.index('btn btn-sm btn-danger'))
        page = self.client.get(reverse('editor_data_dataset', args=[self.dataset.pk])).content.decode()
        self.assertIn('Survey A', page.split('data-testid="used-by"')[1])

    def test_a_report_that_reads_the_dataset_is_listed(self):
        """
        GIVEN a report whose map block reads the answers to a geo question of survey A
        WHEN the owner opens that answers dataset's page
        THEN the page names the report among the places that use it
        """
        from data.links import used_by
        from reports.models import Report, ReportBlock
        where = Question.objects.create(survey_section=self.section_a, code='Q_WHERE', name='Where',
                                        input_type='point')
        report = Report.objects.create(survey=self.survey_a, slug='what-we-heard',
                                       intro={'title': {'en': 'What we heard'}})
        block = ReportBlock.objects.create(report=report, block_type='map', question=where)
        ReportBlock.objects.create(report=report, block_type='map', question=where, order=1)

        places = [p for p in used_by(block.dataset) if p.kind == 'report']
        page = self.client.get(reverse('editor_data_dataset', args=[block.dataset.pk])).content.decode()

        self.assertEqual([p.label for p in places], ['What we heard'])
        self.assertIn('What we heard', page.split('data-testid="used-by"')[1])

    def test_deleting_removes_the_links(self):
        """
        GIVEN the dataset is linked into survey A and a Site, and no question is bound to it
        WHEN the owner confirms the delete
        THEN the dataset, its layer and its links are gone and survey A lists no layer
        """
        self.link(self.survey_a)
        _site, block = self.site_with_block()
        self.client.post(reverse('editor_data_delete', args=[self.dataset.pk]))
        self.assertFalse(Dataset.objects.filter(pk=self.dataset.pk).exists())
        self.assertFalse(SurveyMapLayer.objects.filter(pk=self.layer.pk).exists())
        self.assertFalse(DatasetLink.objects.exists())
        self.assertEqual(layers_for(self.survey_a).count(), 0)
        block.refresh_from_db()
        self.assertIsNone(block.data['dataset'])

    def test_bound_question_blocks_the_delete(self):
        """
        GIVEN a question of survey A is bound to the linked layer
        WHEN the owner confirms the delete
        THEN nothing is deleted and the page names the question
        """
        self.link(self.survey_a)
        Question.objects.create(survey_section=self.section_a, code='OBJ', name='Rate the trees',
                                input_type='layer_objects', layer=self.layer)
        r = self.client.post(reverse('editor_data_delete', args=[self.dataset.pk]))
        self.assertTrue(Dataset.objects.filter(pk=self.dataset.pk).exists())
        self.assertIn('Rate the trees', r.content.decode())


class MemoryRulesTest(_LinkFixture):
    """Requirement: Linked layers keep the memory rules."""

    def test_site_page_carries_the_url_not_the_features(self):
        """
        GIVEN a published Site whose map block shows the dataset
        WHEN a visitor opens the page
        THEN the page carries the block's GeoJSON URL and none of the dataset's coordinates
        """
        site, block = self.site_with_block()
        self.client.logout()
        html = self.client.get(reverse('site_public', args=[site.slug])).content.decode()
        self.assertIn(reverse('site_block_dataset', args=[site.slug, block.pk]), html)
        self.assertNotIn('51.5678', html)
        self.assertNotIn('Lime', html)

    def test_respondent_metadata_carries_the_url(self):
        """
        GIVEN survey A links the dataset
        WHEN the respondent map's layer metadata is built
        THEN it names the layer's gated URL and holds no feature
        """
        from survey.layers import build_map_layers_metadata
        self.link(self.survey_a)
        meta = build_map_layers_metadata(self.survey_a)
        self.assertEqual([m['id'] for m in meta], [self.layer.pk])
        self.assertNotIn('51.5678', json.dumps(meta))
