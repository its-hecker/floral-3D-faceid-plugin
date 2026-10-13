# SPDX-License-Identifier: Apache-2.0
"""Regress the namespace-order failure on the actual prepared Blueprint output."""

import contextlib
import io
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import prepare

FACE = (ROOT / "faceid.mk").is_file()


class PreparedNamespaceTests(unittest.TestCase):
    def test_namespace_precedes_named_modules_and_retains_licenses(self):
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory)
            plugin = rom / "plugin"
            plugin.mkdir()
            paths = ["Android.bp.in", "native/camera/Android.bp.in" if FACE else "settings/Android.bp.in"]
            for relative in paths:
                target = plugin / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            xml = rom / "config.xml"
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(prepare, "verify_all"))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                if FACE:
                    stack.enter_context(patch.object(prepare, "check_framework", return_value=("already applied", None)))
                    vendor = rom / "vendor/google/coral"
                    vendor.mkdir(parents=True)
                    (vendor / "Android.bp").write_text('soong_namespace {\n    imports: ["hardware/google/interfaces"],\n}\n')
                    for filename in ["faceauth_config.yaml", "faceauth_v1.mdt"]:
                        path = vendor / "proprietary/vendor/firmware" / filename
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.touch()
                    xml.write_text('<resources><string-array name="config_biometric_sensors"><item>0:8:15</item></string-array></resources>')
                    prepare.prepare(rom, vendor, [xml], root=plugin)
                else:
                    policy = rom / "policy"
                    policy.mkdir()
                    (policy / "types.te").write_text("type persist_oslo_file;\ntype vendor_aware_available_prop;\n")
                    xml.write_text('<resources><string-array name="config_pluginAllowlist"><item>com.example.keep</item></string-array></resources>')
                    prepare.prepare(rom, [xml], [policy], root=plugin)
            bp = (plugin / "Android.bp").read_text()
            modules = re.findall(r"(?m)^([A-Za-z_]\w*)\s*\{", bp)
            self.assertEqual(modules[0], "soong_namespace", "Soong rejects a namespace after a named module")
            self.assertEqual(modules.count("soong_namespace"), 1)
            self.assertIn("package", modules)
            self.assertIn("license", modules)
            self.assertIn('license_text: ["LICENSE", "NOTICE"]', bp)
            if FACE:
                self.assertIn('imports: ["vendor/google/coral", "hardware/google/interfaces"]', bp)
                self.assertNotIn("@NAMESPACE_IMPORTS@", bp)


if __name__ == "__main__":
    unittest.main()
