import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('helper', ROOT / 'scripts/prepare-cloudflared-prebuilt.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class PrebuiltTests(unittest.TestCase):
    def test_release_selection(self):
        asset = dict(name=helper.ASSET, size=120, digest='sha256:' + 'a' * 64,
                     browser_download_url=f'https://github.com/{helper.REPOSITORY}/releases/download/2026.10.7/{helper.ASSET}')
        release = dict(tag_name='2026.10.7', assets=[asset])
        self.assertEqual(helper.select_release(release, release)[0], '2026.10.7')
        for changes in ({'tag_name': '2026.5.0'}, {'prerelease': True}, {'tag_name': '../bad'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                helper.select_release(dict(release, **changes), release)
        for changes in ({'size': 0}, {'digest': ''}, {'name': 'wrong'}, {'browser_download_url': 'https://example.com'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                helper.select_release(dict(release, assets=[dict(asset, **changes)]), release)

    def test_binary(self):
        data = bytearray(120)
        data[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HH', data, 16, 2, 183)
        struct.pack_into('<Q', data, 32, 64)
        struct.pack_into('<HH', data, 54, 56, 1)
        struct.pack_into('<I', data, 64, 1)
        def asset(binary):
            return dict(size=len(binary), digest='sha256:' + hashlib.sha256(binary).hexdigest())
        helper.verify_binary(data, asset(data))
        with self.assertRaises(ValueError):
            helper.verify_binary(data + b'x', asset(data))
        with self.assertRaises(ValueError):
            helper.verify_binary(data, dict(asset(data), digest='sha256:' + '0' * 64))
        for offset, value in ((18, 62), (64, 3), (54, 0)):
            changed = bytearray(data)
            changed[offset] = value
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                helper.verify_binary(changed, asset(changed))

    def test_template(self):
        recipe = (ROOT / 'packages/cloudflared-prebuilt/Makefile').read_text()
        self.assertIn('$(call BuildPackage,cloudflared)', recipe)
        self.assertNotIn('golang', recipe)
        for path in ('/usr/bin/cloudflared', '/etc/config/cloudflared', '/etc/cloudflared/', '/etc/init.d/cloudflared'):
            self.assertIn(path, recipe)
        for name in ('sample_config.yml', 'cloudflared.config', 'cloudflared.init'):
            self.assertIn('$(CURDIR)/files/' + name, recipe)


if __name__ == '__main__':
    unittest.main()
