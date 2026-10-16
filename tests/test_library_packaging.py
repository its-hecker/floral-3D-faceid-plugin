# SPDX-License-Identifier: Apache-2.0
"""Check prepared library ownership with and without a base multilib provider."""

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
import verify_ready


class LibraryPackagingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.rom = Path(self.directory.name)
        self.plugin = self.rom / "plugin"
        for relative in ("Android.bp.in", "native/camera/Android.bp.in"):
            target = self.plugin / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        self.vendor = self.rom / "vendor/google/coral"
        self.vendor.mkdir(parents=True)
        (self.vendor / "Android.bp").write_text("soong_namespace {\n}\n")
        for filename in ("faceauth_config.yaml", "faceauth_v1.mdt"):
            target = self.vendor / "proprietary/vendor/firmware" / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        self.xml = self.rom / "config.xml"
        self.xml.write_text('<resources><string-array name="config_biometric_sensors"><item>0:8:15</item></string-array></resources>')
        self.pinned = self.plugin / "proprietary/compat/libstagefright_foundation-v33.so"
        self.pinned.parent.mkdir(parents=True)
        self.pinned.write_bytes(b"verified v33 arm64 fixture")

    def base_provider(self, content=None):
        compat = self.rom / "hardware/lineage/compat"
        compat.mkdir(parents=True)
        (compat / "Android.bp").write_text('''cc_prebuilt_library_shared {
    name: "libstagefright_foundation-v33",
    system_ext_specific: true,
    vendor_available: true,
    target: {
        android_arm: { srcs: ["vndk/v33/arm/libstagefright_foundation-v33.so"] },
        android_arm64: { srcs: ["vndk/v33/arm64/libstagefright_foundation-v33.so"] },
    },
    compile_multilib: "both",
}
''')
        for arch, data in (("arm", b"keep existing 32-bit ABI"),
                           ("arm64", self.pinned.read_bytes() if content is None else content)):
            target = compat / "vndk/v33" / arch / self.pinned.name
            target.parent.mkdir(parents=True)
            target.write_bytes(data)
        return compat

    def generate(self):
        with patch.object(prepare, "verify_all"), \
                patch.object(prepare, "check_framework", return_value=("already applied", None)), \
                contextlib.redirect_stdout(io.StringIO()):
            prepare.prepare(self.rom, self.vendor, [self.xml], root=self.plugin)
        return (self.plugin / "Android.bp").read_text()

    def test_matching_base_provider_is_shared_and_both_arches_are_preserved(self):
        compat = self.base_provider()
        before = {p: p.read_bytes() for p in compat.rglob("*") if p.is_file()}
        bp = self.generate()
        self.assertNotIn('name: "FloralFaceIDV33Foundation"', bp)
        self.assertIn('"libstagefright_foundation-v33"', bp)
        self.assertIn('"libstagefright_foundation-v33"', (self.plugin / "native/camera/Android.bp").read_text())
        self.assertIn("FLORAL_FACEID_FOUNDATION_MODULE := libstagefright_foundation-v33",
                      (self.plugin / "generated/profile.mk").read_text())
        self.assertEqual(before, {p: p.read_bytes() for p in compat.rglob("*") if p.is_file()})
        expected = {"FloralFaceIDCitadelImpl": "android.hardware.keymaster@4.1-impl.nos",
                    "FloralFaceIDCalibrationProto": "libface-calibration-proto",
                    "FloralFaceIDEnrollmentProto": "libface-enroll-proto",
                    "FloralFaceIDAuthUtil": "libfaceauth-util",
                    "FloralFaceIDAirbrushClient": "libairbrush-pixel"}
        for name, replaced in expected.items():
            block = re.search(r'(?ms)^cc_prebuilt_library_shared\s*\{\s*name: "' + name + r'",.*?^\}', bp).group()
            self.assertIn('overrides: ["' + replaced + '"]', block)

    def test_base_without_provider_keeps_the_pinned_plugin_fallback(self):
        bp = self.generate()
        self.assertIn('name: "FloralFaceIDV33Foundation"', bp)
        self.assertIn("FLORAL_FACEID_FOUNDATION_MODULE := FloralFaceIDV33Foundation",
                      (self.plugin / "generated/profile.mk").read_text())

    def test_different_base_binary_is_refused_before_output_is_written(self):
        self.base_provider(b"different ABI")
        with self.assertRaisesRegex(ValueError, "differs from the pinned Face ID ABI"):
            self.generate()
        self.assertFalse((self.plugin / "Android.bp").exists())

    def test_shared_provider_change_invalidates_prepared_outputs(self):
        compat = self.base_provider()
        self.generate()
        with patch.object(verify_ready, "verify_all"):
            verify_ready.verify(self.plugin)
            (compat / "Android.bp").write_text("// changed after preparation\n")
            with self.assertRaisesRegex(ValueError, "Prepared source changed"):
                verify_ready.verify(self.plugin)


if __name__ == "__main__":
    unittest.main()
