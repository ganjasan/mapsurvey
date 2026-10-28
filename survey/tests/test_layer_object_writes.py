"""Tests for the `layer-object-writes` capability (openspec/specs/layer-object-writes/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
import json
from survey.models import Organization, SurveyHeader, SurveySection, Membership
from survey.tests.helpers import _objects_layer


class LayerObjectWriteLockTest(TestCase):
    """Writers of one layer are serialised (change serialise-layer-object-writes).

    Key generation, the caps count and `rebuild_layer` each read the layer's
    objects and then act on what they read, so concurrent writers collided on a
    generated key (`layerobject_unique_key_per_layer`, PostHog 01a0abb4) and
    overwrote each other's derived GeoJSON. A real race needs two connections;
    what these pin is that the lock is taken at all, and that taking it does not
    undo the layer memory diet."""

    GEOJSON_COLUMN = '"survey_surveymaplayer"."geojson_gz"'

    def setUp(self):
        self.org = Organization.objects.create(name="Lock Org")
        self.owner = User.objects.create_user(username='lockowner', password='pw12345678')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="lock_survey", organization=self.org, redirect_url="/thanks/", created_by=self.owner,
        )
        SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        self.layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')
        self.client.login(username='lockowner', password='pw12345678')

    def _u(self, name, **kw):
        kw.setdefault('survey_uuid', self.survey.uuid)
        kw.setdefault('layer_id', self.layer.pk)
        return reverse(name, kwargs=kw)

    def _create(self, **payload):
        payload.setdefault('geometry', {'type': 'Point', 'coordinates': [-88.09, 38.73]})
        return self.client.post(self._u('editor_layer_objects_collection'),
                                data=json.dumps(payload), content_type='application/json')

    def _locking_selects(self, queries):
        return [q['sql'] for q in queries
                if 'survey_surveymaplayer' in q['sql'] and 'FOR UPDATE' in q['sql'].upper()]

    def test_creating_an_object_locks_the_layer_row(self):
        """
        GIVEN an owner drawing a new object
        WHEN the create endpoint runs
        THEN it takes a row lock on the layer, so a concurrent writer cannot allocate
             the same key or rebuild from a stale snapshot
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            response = self._create()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._locking_selects(ctx.captured_queries),
                        "no SELECT ... FOR UPDATE on the layer row")

    def test_the_lock_does_not_select_the_geojson_column(self):
        """
        GIVEN the layer memory diet: `geojson_gz` is up to 10 MB and a worker keeps
              the resident memory of its largest request for life
        WHEN the create endpoint locks the layer row
        THEN the locking query selects no geometry text
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self._create().status_code, 201)
        for sql in self._locking_selects(ctx.captured_queries):
            self.assertNotIn(self.GEOJSON_COLUMN, sql)

    def test_every_mutating_path_locks(self):
        """
        GIVEN each mutating endpoint of the object editor
        WHEN it writes and rebuilds the layer
        THEN each one takes the layer row lock, not only the create path
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        key = self._create().json()['row']['key']
        cases = {
            'patch': ('patch', self._u('editor_layer_object', key=key), {'title': 'Renamed'}),
            'geometry': ('post', self._u('editor_layer_object_geometry', key=key),
                         {'geometry': {'type': 'Point', 'coordinates': [-88.0, 38.7]}}),
            'bulk': ('post', self._u('editor_layer_objects_bulk'),
                     {'action': 'set_category', 'category': 'x', 'keys': [key]}),
            'delete': ('delete', self._u('editor_layer_object', key=key), {}),
        }
        for label, (method, url, payload) in cases.items():
            with self.subTest(path=label):
                with CaptureQueriesContext(connection) as ctx:
                    response = getattr(self.client, method)(
                        url, data=json.dumps(payload), content_type='application/json')
                self.assertEqual(response.status_code, 200)
                self.assertTrue(self._locking_selects(ctx.captured_queries),
                                f"{label} wrote the layer without locking it")

    def test_generated_key_skips_the_ones_already_taken(self):
        """
        GIVEN a layer whose keys already occupy the generated sequence, with a gap
        WHEN an object is created without a key
        THEN the generated key collides with nothing in the layer
        """
        from survey.models import LayerObject
        from django.contrib.gis.geos import Point
        for key in ('o-1', 'o-2', 'o-4'):
            LayerObject.objects.create(layer=self.layer, key=key, title=key,
                                       geometry=Point(0, 0, srid=4326), position=0)
        before = set(self.layer.items.values_list('key', flat=True))
        response = self._create()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn(response.json()['row']['key'], before)
        keys = list(self.layer.items.values_list('key', flat=True))
        self.assertEqual(len(keys), len(set(keys)))

    def test_a_supplied_key_that_is_taken_is_a_client_error(self):
        """
        GIVEN a create request naming a key the layer already holds
        WHEN it is POSTed
        THEN it is refused with 400 naming the key, never a 500 from the constraint
        """
        taken = self.layer.items.first().key
        response = self._create(key=taken)
        self.assertEqual(response.status_code, 400)
        self.assertIn(taken, response.json()['error'])


class LayerObjectWriteRaceTest(TransactionTestCase):
    """Two real writers racing for one generated key (change serialise-layer-object-writes).

    The sibling query-capture tests prove the `FOR UPDATE` is issued; this one
    runs the collision that was reported. Two threads on two connections create
    an object in the same layer, rendezvousing inside key allocation so both are
    holding the same view of the layer's keys — which is exactly how two creates
    landed on `o-2` and the second died on `layerobject_unique_key_per_layer`
    (PostHog 01a0abb4). Under the lock the second writer cannot get in until the
    first has committed, so the barrier times out harmlessly and the keys differ.

    `TransactionTestCase` because the threads need committed state across
    connections; it is the only one in this suite and truncates rather than
    rolls back, so it is slower than its siblings."""

    def setUp(self):
        self.org = Organization.objects.create(name="Race Org")
        self.owner = User.objects.create_user(username='raceowner', password='pw12345678')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="race_survey", organization=self.org, redirect_url="/thanks/", created_by=self.owner,
        )
        SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        self.layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')

    def test_two_concurrent_creates_get_distinct_keys(self):
        """
        GIVEN two requests creating an object in one layer at the same time, neither
              supplying a key, meeting inside key allocation
        WHEN both run on their own connection
        THEN both succeed with keys of their own, and neither hits the unique constraint
        """
        import threading
        from django.db import connections
        from survey import layer_object_views

        url = reverse('editor_layer_objects_collection',
                      kwargs={'survey_uuid': self.survey.uuid, 'layer_id': self.layer.pk})
        payload = json.dumps({'geometry': {'type': 'Point', 'coordinates': [-88.09, 38.73]}})
        original = layer_object_views._next_key
        # Both writers wait here. Unlocked they meet and read the same keys; locked
        # the second is still outside the transaction, so this times out and the
        # barrier breaks — which is the point, not a failure.
        barrier = threading.Barrier(2, timeout=2)

        def rendezvous(layer, prefix='o'):
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                pass
            return original(layer, prefix)

        results = []
        lock = threading.Lock()

        def create():
            client = Client()
            client.login(username='raceowner', password='pw12345678')
            try:
                response = client.post(url, data=payload, content_type='application/json')
                body = response.json() if response['Content-Type'].startswith('application/json') else {}
                with lock:
                    results.append((response.status_code, body.get('row', {}).get('key')))
            except Exception as exc:
                with lock:
                    results.append((f'{type(exc).__name__}: {exc}', None))
            finally:
                connections.close_all()

        layer_object_views._next_key = rendezvous
        try:
            threads = [threading.Thread(target=create) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
                self.assertFalse(t.is_alive(), "a create thread never finished")
        finally:
            layer_object_views._next_key = original

        self.assertEqual([r[0] for r in results], [201, 201], results)
        keys = [r[1] for r in results]
        self.assertEqual(len(set(keys)), 2, f"both creates took the same key: {keys}")
        stored = list(self.layer.items.values_list('key', flat=True))
        self.assertEqual(len(stored), len(set(stored)))
        self.assertEqual(self.layer.items.count(), 5)
