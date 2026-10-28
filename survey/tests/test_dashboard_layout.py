"""Tests for the `dashboard-layout` capability (openspec/specs/dashboard-layout/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.conf import settings as dj_settings


class DashboardCardLayoutTest(TestCase):
    """Survey cards fit a phone screen whatever the survey name (change start-cards-one-click)."""

    def test_grid_tracks_cannot_grow_to_an_unbreakable_name(self):
        """
        GIVEN the dashboard template (a snake_case survey name pushed every card off a phone)
        WHEN its card grid CSS is read
        THEN no track is a bare 1fr -- which is minmax(auto, 1fr) and grows to the widest
             word -- and survey names may wrap anywhere
        """
        from pathlib import Path
        from django.conf import settings as dj_settings
        css = Path(dj_settings.BASE_DIR, 'survey', 'templates', 'editor.html').read_text()

        self.assertNotIn('grid-template-columns: 1fr;', css)
        self.assertIn('.dashboard-grid { grid-template-columns: minmax(0, 1fr); }', css)
        self.assertIn('minmax(min(300px, 100%), 1fr)', css)
        start = css.index('\n    .card-name {')
        name_rule = css[start:css.index('}', start)]
        self.assertIn('overflow-wrap: anywhere', name_rule)
