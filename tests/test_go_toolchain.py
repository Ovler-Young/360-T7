from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / '2512-diy-part2.sh').read_text().split("<<'PY_TOOLCHAIN'\n", 1)[1].split('\nPY_TOOLCHAIN', 1)[0]


class GoToolchainTests(unittest.TestCase):
    def test_default_upgrade_and_security_floor(self):
        for patch in (2, 3, 4):
            with self.subTest(patch=patch), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                golang = root / 'feeds/packages/lang/golang'
                golang.mkdir(parents=True)
                values = golang / 'golang-values.mk'
                values.write_text('GO_DEFAULT_VERSION:=1.26\n')
                for name in ('sing-box', 'tailscale'):
                    package = root / f'feeds/packages/net/{name}'
                    package.mkdir(parents=True)
                    (package / 'Makefile').write_text('PKG_BUILD_DEPENDS:=golang/host\n')
                recipe = root / 'recipe'
                recipe.write_text(f'PKG_NAME:=golang1.27\nGO_VERSION_MAJOR_MINOR:=1.27\nGO_VERSION_PATCH:={patch}\nPKG_HASH:=' + 'a' * 64 + '\n')
                helper = root / 'helper'
                helper.write_text('include ../golang-values.mk\n  $(if $(PKG_HOST_ONLY),BUILDONLY:=1)\n')
                result = subprocess.run([sys.executable, '-c', SCRIPT, str(recipe), str(helper)], cwd=root,
                                        capture_output=True, text=True)
                if patch < 3:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(values.read_text(), 'GO_DEFAULT_VERSION:=1.26\n')
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(values.read_text(), 'GO_DEFAULT_VERSION:=1.27\n')
                    self.assertEqual((golang / 'golang1.27/Makefile').read_text(), recipe.read_text())
                    self.assertEqual((golang / 'golang-version.mk').read_text(), helper.read_text())
