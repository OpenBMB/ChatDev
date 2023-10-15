import os
import unittest


pg_header = os.path.join("src_c", "include", "_pygame.h")


class VersionTest(unittest.TestCase):
    @unittest.skipIf(
        not os.path.isfile(pg_header), "Skipping because we cannot find _pygame.h"
    )
    def test_pg_version_consistency(self):
        from pygame import version

        pgh_major = -1
        pgh_minor = -1
        pgh_patch = -1
        import re

        major_exp_search = re.compile(r"define\s+PG_MAJOR_VERSION\s+([0-9]+)").search
        minor_exp_search = re.compile(r"define\s+PG_MINOR_VERSION\s+([0-9]+)").search
        patch_exp_search = re.compile(r"define\s+PG_PATCH_VERSION\s+([0-9]+)").search
        with open(pg_header) as f:
            for line in f:
                if pgh_major == -1:
                    m = major_exp_search(line)
                    if m:
                        pgh_major = int(m.group(1))
                if pgh_minor == -1:
                    m = minor_exp_search(line)
                    if m:
                        pgh_minor = int(m.group(1))
                if pgh_patch == -1:
                    m = patch_exp_search(line)
                    if m:
                        pgh_patch = int(m.group(1))
        self.assertEqual(pgh_major, version.vernum[0])
        self.assertEqual(pgh_minor, version.vernum[1])
        self.assertEqual(pgh_patch, version.vernum[2])

    def test_sdl_version(self):
        from pygame import version

        self.assertEqual(len(version.SDL), 3)


if __name__ == "__main__":
    unittest.main()
