"""Package restoration source checks run offline; no firmware compilation."""

from io import BytesIO
import importlib.util
import os
from pathlib import Path
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prepare_network_tools", ROOT / "scripts/prepare-network-tools.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def archive(name, content=None):
    if content is None:
        content = os.urandom(2048)
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
        entry = tarfile.TarInfo(name)
        entry.size = len(content)
        tf.addfile(entry, BytesIO(content))
    return buffer.getvalue()


class PublicNetworkToolsTests(unittest.TestCase):
    def test_only_safe_source_tags_selected(self):
        version, tag = mod.wrtbwmon_tag([
            {"name": "0.35"}, {"name": "0.37_ipv6"},
            {"name": "0.37"}, {"name": "../evil"}, {"name": "0.36"}
        ])
        self.assertEqual((version, tag), ("0.37", "0.37_ipv6"))

    def test_tar_validation_rejects_mismatched_and_unsafe_paths(self):
        data = archive("ndisc6-1.0.9/configure")
        self.assertEqual(len(mod.verify_tar(data, "ndisc6-1.0.9", ("configure",))), 64)
        with self.assertRaises(ValueError):
            mod.verify_tar(data, "ndisc6-1.0.9", ("COPYING",))
        with self.assertRaises(ValueError):
            mod.verify_tar(archive("../unsafe"), "ndisc6-1.0.9", ("configure",))

    def test_custom_sources_precede_feed_metadata_index(self):
        script = (ROOT / "2512-diy-part2.sh").read_text()
        self.assertLess(script.index("scripts/prepare-network-tools.py"),
                        script.index("./scripts/feeds update -i packages"))
        self.assertTrue((ROOT / "packages/ndisc6/Makefile").exists())
        self.assertTrue((ROOT / "packages/wrtbwmon/Makefile").exists())


if __name__ == "__main__":
    unittest.main()
