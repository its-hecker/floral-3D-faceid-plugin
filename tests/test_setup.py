#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import prepare


class SensorTests(unittest.TestCase):
    def config(self, text):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/"config.xml";path.write_text(text);return path

    def test_preserves_fingerprint_and_chooses_unused_face_id(self):
        p=self.config('<resources><string-array name="config_biometric_sensors"><item>0:2:15</item><item>2:4:15</item></string-array></resources>')
        self.assertEqual(prepare.sensor_config([p]),(["0:2:15","2:4:15","1:8:15"],1))

    def test_active_overlay_has_precedence(self):
        base=self.config('<resources><string-array name="config_biometric_sensors"><item>0:2:15</item></string-array></resources>')
        override=self.config('<resources><string-array name="config_biometric_sensors"><item>3:2:15</item><item>8:8:15</item></string-array></resources>')
        self.assertEqual(prepare.sensor_config([base,override]),(["3:2:15","8:8:15"],8))

    def test_does_not_reclassify_an_existing_weak_face_sensor(self):
        p=self.config('<resources><string-array name="config_biometric_sensors"><item>0:8:255</item></string-array></resources>')
        with self.assertRaises(ValueError): prepare.sensor_config([p])

    def test_duplicate_ids_and_requested_collision_are_rejected(self):
        p=self.config('<resources><string-array name="config_biometric_sensors"><item>0:2:15</item><item>0:8:15</item></string-array></resources>')
        with self.assertRaises(ValueError): prepare.sensor_config([p])
        p=self.config('<resources><string-array name="config_biometric_sensors"><item>4:2:15</item></string-array></resources>')
        with self.assertRaises(ValueError): prepare.sensor_config([p],4)


if __name__ == "__main__":unittest.main()
