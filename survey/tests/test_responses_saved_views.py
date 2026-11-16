"""Spec: responses-saved-views (change data-analysis-views, #692, epic #712).

The Responses table's filter saved as a view of the survey's responses dataset: stored by question
CODE, listed on the table, re-applied when opened — also after the question rows were replaced by
publishing — and managed like any other view.
"""
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_member, make_pro_org, make_v1_survey
from data.models import Dataset, DatasetView
from survey.models import Answer, Question, SurveySession

TRANSPORT = [{'code': 1, 'name': 'Car'}, {'code': 2, 'name': 'Bike'}]


class _Fixture(TestCase):
    """Four answered sessions: two approved cyclists, one approved driver, one cyclist not yet approved."""

    def setUp(self):
        self.org, self.owner = make_pro_org('SavedViewOrg', 'savedviewowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Travel', status='published')
        self.transport = Question.objects.create(survey_section=self.section, code='TRANSPORT', name='Transport',
                                                 input_type='choice', choices=TRANSPORT)
        self.sessions = {}
        for key, choice, status in (('bike1', 2, 'approved'), ('bike2', 2, 'approved'),
                                    ('car', 1, 'approved'), ('bike_new', 2, '')):
            s = SurveySession.objects.create(survey=self.survey, validation_status=status)
            Answer.objects.create(survey_session=s, question=self.transport, selected_choices=[choice])
            self.sessions[key] = s
        self.login(self.owner)
        self.table = reverse('analytics_table', args=[self.survey.uuid])
        self.save_url = reverse('analytics_view_save', args=[self.survey.uuid])

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def save(self, name='Approved cyclists', **extra):
        data = {'name': name, 'version': 'all', 'cf_validation_status': 'v:approved',
                f'cf_{self.transport.pk}': 'v:Bike'}
        data.update(extra)
        return self.client.post(self.save_url, data)

    def rows(self, **params):
        page = self.client.get(self.table, params)
        return sorted(row['id'] for row in page.context['rows']), page


class SaveTest(_Fixture):
    """Requirement: A Responses filter is saved as a view of the survey's responses."""

    def test_saving_the_current_filter(self):
        """
        GIVEN the table filtered to status approved and to Bike in the transport question
        WHEN an editor saves it as "Approved cyclists"
        THEN the responses dataset has a view of kind responses whose columns name the status
             column and the question's code, not its row id
        """
        r = self.save()
        self.assertEqual(r.status_code, 201, r.content)
        view = DatasetView.objects.get()
        self.assertEqual((view.kind, view.name, view.dataset.kind, view.dataset.survey_id),
                         ('responses', 'Approved cyclists', Dataset.KIND_RESPONSES, self.survey.id))
        self.assertEqual(view.config['columns'], {'validation_status': 'v:approved', 'q:TRANSPORT': 'v:Bike'})
        self.assertNotIn(str(self.transport.pk), str(view.config))

    def test_a_viewer_cannot_save(self):
        """
        GIVEN a member with the viewer role
        WHEN they post a view
        THEN the call is refused and nothing is saved
        """
        viewer = make_member(self.org, 'savedviewviewer', role='viewer')
        self.login(viewer)
        self.assertEqual(self.save().status_code, 403)
        self.assertFalse(DatasetView.objects.exists())

    def test_a_name_is_required(self):
        """
        GIVEN a filtered table
        WHEN an editor saves a view without a name
        THEN the view is refused
        """
        self.assertEqual(self.save(name='').status_code, 422)
        self.assertFalse(DatasetView.objects.exists())

    def test_an_unfiltered_table_is_not_a_view(self):
        """
        GIVEN a table with no filter
        WHEN an editor saves it
        THEN the view is refused: it would show every response
        """
        r = self.client.post(self.save_url, {'name': 'Everything', 'sort': 'start_datetime', 'dir': 'asc'})
        self.assertEqual(r.status_code, 422)


class OpenTest(_Fixture):
    """Requirement: Opening a saved view applies the same filter."""

    def setUp(self):
        super().setUp()
        self.save()
        self.view = DatasetView.objects.get()
        self.cyclists = sorted([self.sessions['bike1'].pk, self.sessions['bike2'].pk])

    def test_opening_the_view(self):
        """
        GIVEN the saved view "Approved cyclists"
        WHEN the table is asked for it
        THEN only the approved cyclists are listed, the table's state form holds the filter, and
             the views menu lists the view
        """
        ids, page = self.rows(view=self.view.pk)
        self.assertEqual(ids, self.cyclists)
        html = page.content.decode()
        self.assertIn(f'name="cf_{self.transport.pk}" value="v:Bike"', html)
        self.assertIn('name="cf_validation_status" value="v:approved"', html)
        self.assertIn(f'?view={self.view.pk}#responses', html)
        self.assertEqual(self.rows()[0], sorted(s.pk for s in self.sessions.values()))

    def test_after_publishing_changes(self):
        """
        GIVEN unpublished changes published since the view was saved, replacing the question rows
        WHEN the view is opened
        THEN the table shows the same responses
        """
        from survey.versioning import clone_survey_for_draft, publish_draft
        publish_draft(clone_survey_for_draft(self.survey), force=True)
        self.assertFalse(Question.objects.filter(pk=self.transport.pk,
                                                 survey_section__survey_header=self.survey).exists())
        ids, _page = self.rows(view=self.view.pk)
        self.assertEqual(ids, self.cyclists)

    def test_the_question_was_deleted(self):
        """
        GIVEN the transport question is gone from every version
        WHEN the view is opened
        THEN the table opens with the remaining filter and no error
        """
        Answer.objects.all().delete()
        self.transport.delete()
        q = Question.objects.create(survey_section=self.section, code='OTHER', name='Other', input_type='text')
        for s in self.sessions.values():
            Answer.objects.create(survey_session=s, question=q, text='x')
        ids, page = self.rows(view=self.view.pk)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(ids, sorted(self.sessions[k].pk for k in ('bike1', 'bike2', 'car')))

    def test_a_view_of_another_survey(self):
        """
        GIVEN a saved view of another survey
        WHEN this survey's table is asked for it
        THEN the view is ignored
        """
        other, section = make_v1_survey(self.org, self.owner, name='Other', status='published')
        q = Question.objects.create(survey_section=section, code='TRANSPORT', name='T', input_type='choice',
                                    choices=TRANSPORT)
        r = self.client.post(reverse('analytics_view_save', args=[other.uuid]),
                             {'name': 'Theirs', f'cf_{q.pk}': 'v:Car'})
        self.assertEqual(r.status_code, 201, r.content)
        ids, _page = self.rows(view=r.json()['id'])
        self.assertEqual(ids, sorted(s.pk for s in self.sessions.values()))


class ManageTest(_Fixture):
    """Requirement: A saved view is managed like any view."""

    def setUp(self):
        super().setUp()
        self.save()
        self.view = DatasetView.objects.get()

    def test_listed_on_the_dataset_page(self):
        """
        GIVEN a saved Responses view
        WHEN an editor opens the responses dataset
        THEN the view is listed with a link that opens it in Responses
        """
        html = self.client.get(reverse('editor_data_dataset', args=[self.view.dataset_id])).content.decode()
        self.assertIn('Approved cyclists', html)
        self.assertIn(f'/analytics/?view={self.view.pk}#responses', html)
        self.assertIn('Open in Responses', html)

    def test_deleting(self):
        """
        GIVEN a saved view nothing uses
        WHEN an editor deletes it
        THEN it is gone from the Responses list
        """
        r = self.client.post(reverse('analytics_view_delete', args=[self.survey.uuid, self.view.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(DatasetView.objects.exists())
        _ids, page = self.rows()
        self.assertNotIn('Approved cyclists', page.content.decode())

    def test_a_view_a_report_uses_stays(self):
        """
        GIVEN a report block that points at the saved view
        WHEN an editor deletes the view
        THEN the call is refused with 409 and the view stays
        """
        from reports.models import Report, ReportBlock
        report = Report.objects.create(organization=self.org, survey=self.survey, slug='travel-report')
        ReportBlock.objects.create(report=report, block_type='text', dataset=self.view.dataset, view=self.view)
        r = self.client.post(reverse('analytics_view_delete', args=[self.survey.uuid, self.view.pk]))
        self.assertEqual(r.status_code, 409)
        self.assertTrue(DatasetView.objects.filter(pk=self.view.pk).exists())
