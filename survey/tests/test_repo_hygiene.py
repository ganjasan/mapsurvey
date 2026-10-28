"""Tests that no capability owns yet: repo-hygiene.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import SimpleTestCase
import re
from django.conf import settings
import os


class RepoHygieneTest(SimpleTestCase):
    """This repository is public; people are named in it only as `lead-NNN`."""

    SCANNED = ("openspec", "docs", ".claude", "CLAUDE.md", "README.md", "TODO.md")
    BINARY = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".mo", ".ico")
    EMAIL = re.compile(r"(?<![\w.%+-])[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[a-z]{2,}")
    # Our own addresses and public mailing lists, deliberately quoted in specs.
    ALLOWED = {
        "konuchovartem@gmail.com",
        "ijepr.conference@gmail.com",
        "ppgis@dgroups.io",
    }
    ALLOWED_DOMAIN = re.compile(
        r"@(?:[\w-]+\.)*(?:mapsurvey\.org|mapsurvey\.ru|example(?:\.[a-z]+)+|[\w-]+\.example|"
        r"test|localhost|li\.org|users\.noreply\.github\.com|anthropic\.com)$",
        re.IGNORECASE,
    )

    def _is_placeholder(self, address):
        local = address.split("@", 1)[0]
        # x@gmail.com, ab@sdsu.edu, victim+1@gmail.com: illustrative, not a person.
        return len(local) <= 2 or local.startswith("victim+")

    def test_no_real_email_addresses_in_docs_and_specs(self):
        """
        GIVEN the tracked docs, specs and agent instructions of this public repository
        WHEN every email address in them is listed
        THEN only our own, public-list or placeholder addresses remain.

        Lead and respondent addresses belong in the private ops repo
        (settings.OPS_DIR); refer to the person as `lead-NNN` here.
        """
        root = settings.BASE_DIR
        if not os.path.isdir(os.path.join(root, "openspec")):
            self.skipTest("specs are not part of this checkout (e.g. the Docker image)")
        offenders = []
        for entry in self.SCANNED:
            top = os.path.join(root, entry)
            paths = [top] if os.path.isfile(top) else [
                os.path.join(d, f) for d, dirs, files in os.walk(top)
                for f in files
                if "worktrees" not in d.split(os.sep)
            ]
            for path in paths:
                if os.path.islink(path) or path.lower().endswith(self.BINARY):
                    continue
                with open(path, encoding="utf-8", errors="ignore") as handle:
                    text = handle.read()
                for address in set(self.EMAIL.findall(text)):
                    if (address.lower() in self.ALLOWED or self.ALLOWED_DOMAIN.search(address)
                            or self._is_placeholder(address)):
                        continue
                    offenders.append(f"{os.path.relpath(path, root)}: {address}")
        self.assertEqual(offenders, [], "real email addresses in the public repo")
