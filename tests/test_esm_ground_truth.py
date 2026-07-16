"""Ground-truth tests against a real Skyrim Special Edition Skyrim.esm.

These tests validate the plugin reader against the game's own master file.
They skip cleanly when no Skyrim.esm is available (set the
ELDER_WEATHERS_SKYRIM_ESM environment variable to point at one).
"""

import os
import unittest
from pathlib import Path

from elder_weathers.esp.reader import PluginReader


def _find_skyrim_esm() -> Path | None:
    env = os.environ.get("ELDER_WEATHERS_SKYRIM_ESM")
    if env and Path(env).is_file():
        return Path(env)
    return None


ESM = _find_skyrim_esm()


@unittest.skipIf(ESM is None, "no Skyrim.esm available (set ELDER_WEATHERS_SKYRIM_ESM)")
class TestVanillaWeatherRecords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = PluginReader(ESM)

    def test_header_is_tes4_master(self):
        header = self.reader.header
        self.assertEqual(header.record_type, "TES4")
        self.assertTrue(header.is_master)

    def test_wthr_group_has_records(self):
        weathers = self.reader.records("WTHR")
        self.assertGreater(len(weathers), 50)  # vanilla SE ships 100+ weathers

    def test_known_vanilla_weather_edids_present(self):
        edids = {r.edid for r in self.reader.records("WTHR")}
        for known in ("SkyrimClear", "SkyrimFog", "SkyrimStormRain"):
            self.assertIn(known, edids)

    def test_clmt_group_has_records(self):
        climates = self.reader.records("CLMT")
        self.assertGreater(len(climates), 0)
        edids = {r.edid for r in climates}
        self.assertIn("SkyrimClimate", edids)

    def test_wthr_records_expose_subrecords(self):
        clear = next(r for r in self.reader.records("WTHR") if r.edid == "SkyrimClear")
        types = [s.type for s in clear.subrecords]
        self.assertEqual(types[0], "EDID")
        # Every SE weather carries the color block and fog distances.
        self.assertIn("NAM0", types)
        self.assertIn("FNAM", types)


if __name__ == "__main__":
    unittest.main()
