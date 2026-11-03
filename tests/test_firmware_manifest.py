"""Exercise 25.12 firmware artifact staging and manifest validation without rebuilding."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build25.12-360t7.yml"
IMAGE = "20261102-25.12immortalwrt-mediatek-filogic-qihoo_360t7-squashfs-sysupgrade.itb"
MANIFEST = IMAGE.removesuffix("-squashfs-sysupgrade.itb") + ".manifest"


def step_script(name):
    workflow = WORKFLOW.read_text()
    section = workflow.split(f"    - name: {name}\n", 1)[1]
    section = section.split("\n    - name:", 1)[0]
    return textwrap.dedent(section.split("      run: |\n", 1)[1])


class FirmwareManifestTests(unittest.TestCase):
    def test_isolated_workflows_and_upload_before_validation(self):
        source = WORKFLOW.read_text()
        self.assertIn("  push:\n    branches:\n      - feat/immortalwrt-25.12-360t7\n", source)
        self.assertNotIn("UPLOAD_RELEASE: true", source)
        self.assertTrue((ROOT / ".github/workflows/build24.10-6.6-360t7.yml").is_file())
        self.assertLess(source.index("    - name: Upload firmware directory"),
                        source.index("    - name: Validate uploaded firmware manifest"))
        self.assertIn("if-no-files-found: error", source)

    def test_required_packages_come_from_explicit_config_not_generated_dependencies(self):
        source = WORKFLOW.read_text()
        capture = source.split('    - name: Load custom configuration\n', 1)[1].split('\n    - name:', 1)[0]
        download = source.split('    - name: Download package\n', 1)[1].split('\n    - name:', 1)[0]
        self.assertIn('"$CONFIG_FILE"', capture)
        self.assertIn('> openwrt/required-packages.txt', capture)
        self.assertNotIn('> required-packages.txt', download)
        # libatomic was selected by Kconfig during the previous CI run,
        # but is not an explicit package selection in 2512-360t7.config.
        config = (ROOT / '2512-360t7.config').read_text()
        required = {line.removeprefix('CONFIG_PACKAGE_').removesuffix('=y')
                    for line in config.splitlines()
                    if line.startswith('CONFIG_PACKAGE_') and line.endswith('=y')}
        self.assertNotIn('libatomic', required)
        # ImmortalWrt 25.12 uses autocore, not the obsolete autocore-arm symbol.
        self.assertIn('autocore', required)
        self.assertNotIn('autocore-arm', required)
        self.assertTrue({'tailscale', 'sing-box', 'cloudflared', 'adguardhome-core',
                         'luci-app-adguardhome', 'kmod-mt7915e', 'apk-openssl'} <= required)

    def run_steps(self, manifest_name=MANIFEST, manifest_content=None, checksum_valid=True,
                  required_packages="adguardhome-core\ncloudflared\n"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "openwrt/bin/targets/mediatek/filogic"
            target.mkdir(parents=True)
            data = b"test FIT image only, never flash"
            (target / IMAGE).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest() if checksum_valid else "0" * 64
            (target / "sha256sums").write_text(f"{digest}  {IMAGE}\n")
            (root / "openwrt/required-packages.txt").write_text(required_packages)
            if manifest_content is None:
                manifest_content = "adguardhome-core - 1\ncloudflared - 1\n"
            if manifest_name:
                (target / manifest_name).write_text(manifest_content)
            env = dict(os.environ)
            env.update(GITHUB_WORKSPACE=str(root), RUNNER_TEMP=str(root / "runner"),
                       GITHUB_ENV=str(root / "github-env"),
                       GITHUB_OUTPUT=str(root / "github-output"),
                       MANIFEST=MANIFEST)
            stage = subprocess.run(["bash", "-e", "-o", "pipefail", "-c",
                                    step_script("Organize files")],
                                   cwd=root, env=env, text=True, capture_output=True)
            artifact = root / "runner/public-firmware"
            if stage.returncode == 0:
                self.assertEqual((artifact / IMAGE).read_bytes(), data)
                self.assertEqual((artifact / "sha256sums").read_text(),
                                 f"{digest}  {IMAGE}\n")
                self.assertIn("status=success", (root / "github-output").read_text())
                self.assertEqual((artifact / MANIFEST).exists(), manifest_name == MANIFEST)
                if manifest_name == MANIFEST:
                    self.assertEqual((artifact / MANIFEST).read_text(), manifest_content)
                validate = subprocess.run(
                    ["bash", "-e", "-o", "pipefail", "-c",
                     step_script("Validate uploaded firmware manifest")],
                    cwd=root, env=env, text=True, capture_output=True
                )
                return stage, validate
            return stage, None

    def test_matching_device_manifest_is_packaged_and_validated(self):
        stage, validate = self.run_steps()
        self.assertEqual(stage.returncode, 0, stage.stderr)
        self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_misnamed_manifest_preserves_image_but_fails_validation(self):
        stage, validate = self.run_steps(manifest_name="immortalwrt-mediatek-filogic.manifest")
        self.assertEqual(stage.returncode, 0, stage.stderr)
        self.assertNotEqual(validate.returncode, 0)
        self.assertIn("Missing matching device manifest", validate.stderr)

    def test_missing_manifest_preserves_image_but_fails_validation(self):
        stage, validate = self.run_steps(manifest_name=None)
        self.assertEqual(stage.returncode, 0, stage.stderr)
        self.assertNotEqual(validate.returncode, 0)

    def test_missing_required_package_preserves_image_but_fails_validation(self):
        stage, validate = self.run_steps(manifest_content="cloudflared - 1\n")
        self.assertEqual(stage.returncode, 0, stage.stderr)
        self.assertNotEqual(validate.returncode, 0)
        self.assertIn("Missing package in manifest: adguardhome-core", validate.stderr)

    def test_versioned_libustream_openssl_satisfies_explicit_selection(self):
        stage, validate = self.run_steps(
            required_packages="adguardhome-core\ncloudflared\nlibustream-openssl\n",
            manifest_content="adguardhome-core - 1\ncloudflared - 1\n"
                             "libustream-openssl20201210 - 2026.03.01-r1\n")
        self.assertEqual(stage.returncode, 0, stage.stderr)
        self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_libustream_alias_does_not_accept_unversioned_lookalikes(self):
        stage, validate = self.run_steps(
            required_packages="adguardhome-core\ncloudflared\nlibustream-openssl\n",
            manifest_content="adguardhome-core - 1\ncloudflared - 1\n"
                             "libustream-openssl-fake - 1\n")
        self.assertEqual(stage.returncode, 0, stage.stderr)
        self.assertNotEqual(validate.returncode, 0)
        self.assertIn("Missing package in manifest: libustream-openssl", validate.stderr)

    def test_forbidden_package_blocks_public_upload(self):
        stage, validate = self.run_steps(
            manifest_content="adguardhome-core - 1\ncloudflared - 1\nlibrespeed-cli-rust - 1\n")
        self.assertNotEqual(stage.returncode, 0)
        self.assertIsNone(validate)
        self.assertIn("Forbidden package in public firmware", stage.stderr)

    def test_chinese_firstboot_package_blocks_public_upload(self):
        stage, validate = self.run_steps(
            manifest_content='adguardhome-core - 1\ncloudflared - 1\ndefault-settings-chn - 29\n')
        self.assertNotEqual(stage.returncode, 0)
        self.assertIsNone(validate)
        self.assertIn('Forbidden package in public firmware', stage.stderr)

    def test_checksum_mismatch_blocks_upload(self):
        stage, validate = self.run_steps(checksum_valid=False)
        self.assertNotEqual(stage.returncode, 0)
        self.assertIsNone(validate)


if __name__ == "__main__":
    unittest.main()
