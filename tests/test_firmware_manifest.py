"""Exercise the actual 25.12 artifact-collection step without rebuilding OpenWrt."""

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


def organize_script():
    workflow = WORKFLOW.read_text()
    section = workflow.split("    - name: Organize files\n", 1)[1]
    section = section.split("\n    - name:", 1)[0]
    return textwrap.dedent(section.split("      run: |\n", 1)[1])


class FirmwareManifestTests(unittest.TestCase):
    def test_branch_scoped_push_does_not_touch_24_10_workflows(self):
        source = WORKFLOW.read_text()
        self.assertIn(
            "  push:\n    branches:\n      - feat/immortalwrt-25.12-360t7\n",
            source,
        )
        self.assertNotIn("UPLOAD_RELEASE: true", source)
        self.assertEqual(
            (ROOT / ".github/workflows/build24.10-6.6-360t7.yml").is_file(),
            True,
        )

    def run_organize(self, manifest_name=MANIFEST, manifest_content=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "openwrt/bin/targets/mediatek/filogic"
            target.mkdir(parents=True)
            data = b"example FIT image (not flashable)"
            (target / IMAGE).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            (target / "sha256sums").write_text(f"{digest}  {IMAGE}\n")
            (root / "openwrt/required-packages.txt").write_text(
                "adguardhome-core\ncloudflared\n"
            )
            if manifest_content is None:
                manifest_content = "adguardhome-core - 1\ncloudflared - 1\n"
            (target / manifest_name).write_text(manifest_content)
            env = dict(os.environ)
            env.update(
                GITHUB_WORKSPACE=str(root),
                RUNNER_TEMP=str(root / "runner"),
                GITHUB_ENV=str(root / "github-env"),
                GITHUB_OUTPUT=str(root / "github-output"),
            )
            result = subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", organize_script()],
                cwd=root, env=env, text=True, capture_output=True
            )
            artifact = root / "runner/public-firmware"
            if result.returncode == 0:
                self.assertEqual((artifact / IMAGE).read_bytes(), data)
                self.assertEqual((artifact / MANIFEST).read_text(), manifest_content)
                self.assertEqual(
                    (artifact / "sha256sums").read_text(), f"{digest}  {IMAGE}\n"
                )
                self.assertIn("status=success", (root / "github-output").read_text())
            return result

    def test_matching_device_manifest_is_packaged(self):
        result = self.run_organize()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_target_wide_manifest_is_not_accepted(self):
        result = self.run_organize(manifest_name="immortalwrt-mediatek-filogic.manifest")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing matching device manifest", result.stderr)

    def test_missing_required_package_fails(self):
        result = self.run_organize(manifest_content="cloudflared - 1\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing package in manifest: adguardhome-core", result.stderr)

    def test_forbidden_package_fails(self):
        result = self.run_organize(
            manifest_content="adguardhome-core - 1\ncloudflared - 1\nlibrespeed-cli-rust - 1\n"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Forbidden package in public firmware", result.stderr)


if __name__ == "__main__":
    unittest.main()
