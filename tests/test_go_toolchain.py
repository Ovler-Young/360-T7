from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / '2512-diy-part2.sh').read_text().split("<<'PY_TOOLCHAIN'\n", 1)[1].split('\nPY_TOOLCHAIN', 1)[0]


class GoToolchainTests(unittest.TestCase):
    def test_tailscale_tracks_supported_release_and_adguard_fw4_layout(self):
        script = (ROOT / '2512-diy-part2.sh').read_text()
        self.assertIn('update_release_package tailscale tailscale/tailscale || exit 1', script)
        self.assertIn('update_release_package sing-box SagerNet/sing-box || exit 1', script)
        self.assertNotIn('adguardhome-legacy-config', script)
        self.assertIn('root/usr/share/nftables.d/ruleset-post/99-adguardhome.nft', script)
        self.assertIn('rm package/luci-app-adguardhome/root/etc/nftables.d/99-adguardhome.nft', script)
        workflow = (ROOT / '.github/workflows/build25.12-360t7.yml').read_text()
        self.assertIn('etc/uci-defaults/99z-default-settings-us', workflow)
        self.assertIn('Unexpected one-time AdGuardHome migration in public image', workflow)
        self.assertIn('Missing AdGuardHome ruleset-post include', workflow)

    def test_adguard_nft_file_moves_outside_fw4_table(self):
        script = (ROOT / '2512-diy-part2.sh').read_text()
        commands = script.split('install -Dm644 package/luci-app-adguardhome/root/etc/nftables.d/99-adguardhome.nft', 1)[1]
        commands = 'install -Dm644 package/luci-app-adguardhome/root/etc/nftables.d/99-adguardhome.nft' + commands.split('\n\n', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / 'package/luci-app-adguardhome/root/etc/nftables.d/99-adguardhome.nft'
            legacy.parent.mkdir(parents=True)
            legacy.write_text('include "/etc/adguardhome.nft"\n')
            result = subprocess.run(['bash', '-e', '-c', commands], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(legacy.exists())
            new = root / 'package/luci-app-adguardhome/root/usr/share/nftables.d/ruleset-post/99-adguardhome.nft'
            self.assertEqual(new.read_text(), 'include "/etc/adguardhome.nft"\n')

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
