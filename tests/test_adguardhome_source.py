import importlib.util
from pathlib import Path
import unittest

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
