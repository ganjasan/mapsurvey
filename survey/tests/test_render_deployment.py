"""Tests for the `render-deployment` capability (openspec/specs/render-deployment/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import SimpleTestCase
import re
import os


class RenderPreviewEnvGroupTest(SimpleTestCase):
    """PR previews get their secrets from the dashboard-made `mapsurvey-shared`
    environment group; `sync: false` values are never copied into a preview."""

    def _services(self):
        import os
        import re
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(root, 'render.yaml')) as fh:
            text = fh.read()
        # One chunk per service, keyed by name: "  - type: …\n    name: <name>".
        chunks = re.split(r'\n  - type: ', text)
        return text, {re.search(r'\n    name: (\S+)', c).group(1): c for c in chunks[1:]}

    def test_web_and_worker_link_the_shared_group(self):
        """
        GIVEN render.yaml
        WHEN the web service and the Celery worker are read
        THEN both link mapsurvey-shared, the group is not declared in the Blueprint
             (a declared group is cloned empty per preview), and the fake
             previewEnvRenderServiceName key is gone
        """
        import re
        text, services = self._services()
        for name in ('mapsurvey', 'mapsurvey-celery'):
            self.assertIn('- fromGroup: mapsurvey-shared', services[name], name)
        self.assertIsNone(re.search(r'^envVarGroups:', text, re.M), 'group declared in the Blueprint')
        self.assertIsNone(re.search(r'^\s+previewEnvRenderServiceName:', text, re.M), 'fake Render key is back')
