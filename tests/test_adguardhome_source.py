import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "adguard_source", ROOT / "scripts/prepare-adguardhome-core.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


class AdGuardSourceTests(unittest.TestCase):
    def setUp(self):
        self.tag = "v0.107.79"
        self.recipe = (
            "PKG_NAME:=adguardhome\nPKG_VERSION:=0.107.79\n"
            "PKG_SOURCE_URL:=https://codeload.github.com/AdguardTeam/AdGuardHome/tar.gz/v$(PKG_VERSION)?\n"
            "PKG_HASH:=" + "a" * 64 + "\nFRONTEND_HASH:=" + "b" * 64 + "\n")
        self.compiler = "GO_VERSION_MAJOR_MINOR:=1.27\nGO_VERSION_PATCH:=3\n"
        self.release = {
            "tag_name": self.tag,
            "draft": False, "prerelease": False,
            "assets": [{
                "name": source.FRONTEND, "size": 2500000,
                "digest": "sha256:" + "b" * 64,
                "browser_download_url": (
                    "https://github.com/AdguardTeam/AdGuardHome/releases/download/"
                    + self.tag + "/" + source.FRONTEND),
            }],
        }

    def test_supported_source_build(self):
        self.assertEqual(
            source.select_release(self.release, self.recipe, "module example\n\ngo 1.26.6\n", self.compiler),
            ("0.107.79", "a" * 64, "b" * 64, "1.27.3"))
        makefile = (ROOT / "packages/adguardhome-core/Makefile").read_text()
        self.assertIn("PKG_BUILD_DEPENDS:=golang/host", makefile)
        self.assertIn("$(call GoBinPackage,adguardhome-core)", makefile)
        self.assertNotIn("files/adguardhome.init", makefile)
        self.assertIn("CONFLICTS:=adguardhome", makefile)

    def test_new_stable_release_uses_real_archive_hash_and_release_frontend(self):
        latest = dict(self.release, tag_name="v0.107.80", assets=[dict(
            self.release["assets"][0],
            digest="sha256:" + "c" * 64,
            browser_download_url=(
                "https://github.com/AdguardTeam/AdGuardHome/releases/download/"
                "v0.107.80/AdGuardHome_frontend.tar.gz"),
        )])
        with self.assertRaisesRegex(ValueError, "actual source archive"):
            source.select_release(latest, self.recipe, "go 1.27.3\n", self.compiler)
        self.assertEqual(
            source.select_release(latest, self.recipe, "go 1.27.3\n",
                                  self.compiler, downloaded_hash="d" * 64),
            ("0.107.80", "d" * 64, "c" * 64, "1.27.3"))
        with self.assertRaisesRegex(ValueError, "Invalid downloaded source"):
            source.select_release(latest, self.recipe, "go 1.27.3\n",
                                  self.compiler, downloaded_hash="not-a-hash")
        with self.assertRaisesRegex(ValueError, "source SHA-256"):
            source.select_release(self.release, self.recipe, "go 1.26.6\n",
                                  self.compiler, downloaded_hash="d" * 64)

    def test_archive_hash_reads_and_validates_actual_tarball(self):
        content = b"module github.com/AdguardTeam/AdGuardHome\ngo 1.27.3\n"
        expected = []

        def fake_curl(arguments, check):
            self.assertTrue(check)
            self.assertIn("https://codeload.github.com/AdguardTeam/AdGuardHome/tar.gz/v0.107.80?", arguments)
            destination = Path(arguments[arguments.index("--output") + 1])
            with tarfile.open(destination, "w:gz") as archive:
                entry = tarfile.TarInfo("AdGuardHome-0.107.80/go.mod")
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
            expected.append(hashlib.sha256(destination.read_bytes()).hexdigest())

        with mock.patch.object(source.subprocess, "run", side_effect=fake_curl):
            digest = source.source_archive_hash("v0.107.80")
            self.assertEqual(digest, expected[0])

    def test_prepare_new_release_writes_matching_dynamic_hashes(self):
        latest = dict(self.release, tag_name="v0.107.80", assets=[dict(
            self.release["assets"][0],
            digest="sha256:" + "c" * 64,
            browser_download_url=(
                "https://github.com/AdguardTeam/AdGuardHome/releases/download/"
                "v0.107.80/AdGuardHome_frontend.tar.gz"),
        )])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compiler = root / "feeds/packages/lang/golang/golang1.27/Makefile"
            compiler.parent.mkdir(parents=True)
            compiler.write_text(self.compiler)
            with mock.patch.object(source, "github_json", return_value=latest), \
                 mock.patch.object(source, "github_raw", side_effect=[self.recipe, "go 1.27.3\n"]), \
                 mock.patch.object(source, "source_archive_hash", return_value="d" * 64) as download:
                source.prepare(root)
                download.assert_called_once_with("v0.107.80")
            self.assertEqual((root / "package/adguardhome-core/release.mk").read_text(),
                             "PKG_VERSION:=0.107.80\nPKG_HASH:=" + "d" * 64 +
                             "\nFRONTEND_HASH:=" + "c" * 64 + "\n")

    def test_reject_stale_or_tampered_assets(self):
        for tamper in (
            {"tag_name": "v0.107.80"},
            {"prerelease": True},
        ):
            with self.subTest(tamper=tamper), self.assertRaises(ValueError):
                source.select_release(dict(self.release, **tamper),
                                      self.recipe, "go 1.26.6\n", self.compiler)
        for change in ({"size": 0}, {"digest": "sha256:" + "0" * 64}):
            asset = dict(self.release["assets"][0], **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                source.select_release(dict(self.release, assets=[asset]),
                                      self.recipe, "go 1.26.6\n", self.compiler)

    def test_requires_supported_go(self):
        for module, compiler in (
            ("go 1.28.0\n", self.compiler),
            ("go 1.26.6\n", "GO_VERSION_MAJOR_MINOR:=1.27\nGO_VERSION_PATCH:=2\n"),
        ):
            with self.subTest(module=module, compiler=compiler), self.assertRaises(ValueError):
                source.select_release(self.release, self.recipe, module, compiler)


if __name__ == "__main__":
    unittest.main()
