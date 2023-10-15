import os
import subprocess
import sys
import unittest


class DocsIncludedTest(unittest.TestCase):
    def test_doc_import_works(self):
        from pygame.docs.__main__ import has_local_docs, open_docs

    @unittest.skipIf("CI" not in os.environ, "Docs not required for local builds")
    def test_docs_included(self):
        from pygame.docs.__main__ import has_local_docs

        self.assertTrue(has_local_docs())

    @unittest.skipIf("CI" not in os.environ, "Docs not required for local builds")
    def test_docs_command(self):
        try:
            subprocess.run(
                [sys.executable, "-m", "pygame.docs"],
                timeout=5,
                # check ensures an exception is raised when the process fails
                check=True,
                # pipe stdout/stderr so that they don't clutter main stdout
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.TimeoutExpired:
            # timeout errors are not an issue
            pass


if __name__ == "__main__":
    unittest.main()
