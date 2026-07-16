"""Region pass: vanilla weather regions redistributed onto EW weathers.

The pass must preserve each region's climate character: a snowy region keeps
its snow share, a rainy coast keeps its rain share. Only Tamriel-worldspace
distribution regions are touched; FX regions and scripted quest weathers are
excluded byte-for-byte.
"""

import struct
import unittest

from elder_weathers.esp.reader import PluginReader
from elder_weathers.esp.region import classify_weather, plan_region_overrides
from elder_weathers.esp.writer import build_weather_plugin
from elder_weathers.model.archetypes import ARCHETYPES
from elder_weathers.model.atmosphere import generate_palette
from tests.test_esm_ground_truth import ESM


@unittest.skipIf(ESM is None, "no Skyrim.esm available (set ELDER_WEATHERS_SKYRIM_ESM)")
class TestClassifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vanilla = PluginReader(ESM)
        cls.by_edid = {r.edid: r for r in cls.vanilla.records("WTHR")}

    def test_known_family_classification(self):
        expected = {
            "SkyrimClear": "clear",
            "SkyrimCloudy": "cloudy",
            "SkyrimOvercastRain": "rain",
            "SkyrimStormRain": "storm",
            "SkyrimFog": "fog",
            "SkyrimOvercastSnow": "snow",
            "SkyrimStormSnow": "snow",
        }
        for edid, want in expected.items():
            self.assertEqual(classify_weather(self.by_edid[edid]), want, edid)

    def test_every_targeted_weather_classifies(self):
        plan = plan_region_overrides(self.vanilla)
        for region_edid, entries in plan.items():
            for archetype, chance in entries:
                self.assertIn(archetype, ARCHETYPES, region_edid)


@unittest.skipIf(ESM is None, "no Skyrim.esm available (set ELDER_WEATHERS_SKYRIM_ESM)")
class TestRegionOverrides(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vanilla = PluginReader(ESM)
        palettes = {name: generate_palette(a) for name, a in ARCHETYPES.items()}
        data = build_weather_plugin(palettes, cls.vanilla)

        import os, tempfile
        fd, cls.path = tempfile.mkstemp(suffix=".esp")
        os.close(fd)
        with open(cls.path, "wb") as f:
            f.write(data)
        cls.plugin = PluginReader(cls.path)
        cls.vanilla_regions = {r.edid: r for r in cls.vanilla.records("REGN")}
        cls.our_regions = {r.edid: r for r in cls.plugin.records("REGN")}
        cls.weather_ids = {w.form_id for w in cls.plugin.records("WTHR")}
        cls.weather_by_id = {w.form_id: w for w in cls.plugin.records("WTHR")}

    @classmethod
    def tearDownClass(cls):
        import os
        os.unlink(cls.path)

    def _shares(self, rdwt: bytes, classify) -> dict[str, int]:
        shares: dict[str, int] = {}
        for off in range(0, len(rdwt), 12):
            fid, chance, _ = struct.unpack_from("<IiI", rdwt, off)
            shares[classify(fid)] = shares.get(classify(fid), 0) + chance
        return shares

    def test_main_distribution_regions_overridden(self):
        for name in ("WeatherTundra", "WeatherSnow", "WeatherCoast",
                     "WeatherPineForest", "WeatherFallForest", "WeatherReach"):
            self.assertIn(name, self.our_regions)

    def test_exclusions_hold(self):
        for edid in self.our_regions:
            self.assertFalse(edid.startswith("FX"), edid)
        self.assertNotIn("WeatherDA02", self.our_regions)      # scripted quest
        self.assertNotIn("SovngardeIntWeather", self.our_regions)  # other worldspace
        self.assertNotIn("WeatherSolitude", self.our_regions)      # city worldspace

    def test_overrides_are_true_overrides(self):
        for edid, ours in self.our_regions.items():
            self.assertEqual(ours.form_id, self.vanilla_regions[edid].form_id, edid)

    def test_rdwt_points_only_at_our_weathers_and_preserves_total(self):
        for edid, ours in self.our_regions.items():
            rdwt = ours.first("RDWT").data
            vanilla_rdwt = self.vanilla_regions[edid].first("RDWT").data
            total = 0
            for off in range(0, len(rdwt), 12):
                fid, chance, _ = struct.unpack_from("<IiI", rdwt, off)
                self.assertIn(fid, self.weather_ids, edid)
                total += chance
            vanilla_total = sum(
                struct.unpack_from("<IiI", vanilla_rdwt, off)[1]
                for off in range(0, len(vanilla_rdwt), 12))
            self.assertEqual(total, vanilla_total, edid)

    def test_region_character_preserved(self):
        vanilla_weathers = {w.form_id: w for w in self.vanilla.records("WTHR")}

        def classify_vanilla(fid):
            return classify_weather(vanilla_weathers[fid])

        def classify_ours(fid):
            edid = self.weather_by_id[fid].edid          # EWSnow -> snow
            return edid[2:].lower()

        for edid, ours in self.our_regions.items():
            want = self._shares(self.vanilla_regions[edid].first("RDWT").data,
                                classify_vanilla)
            got = self._shares(ours.first("RDWT").data, classify_ours)
            self.assertEqual(got, want, edid)

    def test_non_weather_subrecords_untouched(self):
        for edid, ours in self.our_regions.items():
            vanilla = self.vanilla_regions[edid]
            ours_rest = [(s.type, s.data) for s in ours.subrecords if s.type != "RDWT"]
            vanilla_rest = [(s.type, s.data) for s in vanilla.subrecords if s.type != "RDWT"]
            self.assertEqual(ours_rest, vanilla_rest, edid)


if __name__ == "__main__":
    unittest.main()
