"""`mcp-server`: the help centre's tool reference is generated from the registry."""
import importlib.util
from pathlib import Path

from django.test import SimpleTestCase


class McpReferenceFreshnessTest(SimpleTestCase):
    def test_help_reference_matches_the_registry(self):
        """
        GIVEN the help centre's MCP tools page
        WHEN it is rendered again from the current registry
        THEN it is identical -- a tool or description change ships with a regenerated page, out of draft
        """
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'build_mcp_reference.py'
        spec = importlib.util.spec_from_file_location('build_mcp_reference', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from .. import tools
        page = module.PAGE.read_text()
        self.assertEqual(page, module.render(tools.all_tools()),
                         'help/src/content/docs/reference/mcp-tools.md is stale: run python scripts/build_mcp_reference.py')
        self.assertNotIn('draft: true', page)
