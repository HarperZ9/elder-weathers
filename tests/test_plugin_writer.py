"""Round-trip tests for the plugin writer.

The writer's output is parsed back with the same reader that the ground-truth
suite validates against Skyrim.esm, so a pass here means the game-format
reader accepts our own output byte for byte.
"""

import unittest

from elder_weathers.esp.reader import FLAG_LIGHT, FLAG_MASTER, PluginReader
from elder_weathers.esp.weather import WeatherView
from elder_weathers.esp.writer import build_weather_plugin
from elder_weathers.model.archetypes import ARCHETYPES
from elder_weathers.model.atmosphere import generate_palette
from tests.test_esm_ground_truth import ESM


@unittest.skipIf(ESM is None, "no Skyrim.esm available (set ELDER_WEATHERS_SKYRIM_ESM)")
class TestPluginRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vanilla = PluginReader(ESM)
        cls.palettes = {name: generate_palette(a) for name, a in ARCHETYPES.items()}
        cls.plugin_bytes = build_weather_plugin(cls.palettes, cls.vanilla)

        import io, tempfile, os
        fd, cls.path = tempfile.mkstemp(suffix=".esp")
        os.close(fd)
        with open(cls.path, "wb") as f:
            f.write(cls.plugin_bytes)
        cls.reparsed = PluginReader(cls.path)

    @classmethod
    def tearDownClass(cls):
        import os
        os.unlink(cls.path)

    def test_header_is_light_plugin_with_skyrim_master(self):
        header = self.reparsed.header
        self.assertEqual(header.record_type, "TES4")
        self.assertFalse(header.flags & FLAG_MASTER)
        self.assertTrue(header.flags & FLAG_LIGHT)
        masters = [s.data.rstrip(b"\x00").decode() for s in header.all("MAST")]
        self.assertEqual(masters, ["Skyrim.esm"])

    def test_seven_weathers_present(self):
        weathers = self.reparsed.records("WTHR")
        self.assertEqual(len(weathers), 7)
        edids = {w.edid for w in weathers}
        for name in ARCHETYPES:
            self.assertIn(f"EW{name.capitalize()}", edids)

    def test_weather_formids_are_esl_safe_new_records(self):
        for w in self.reparsed.records("WTHR"):
            self.assertEqual(w.form_id >> 24, 0x01)          # module index = 1 master
            self.assertTrue(0x800 <= (w.form_id & 0xFFF) <= 0xFFF)  # ESL object range

    def test_palette_blocks_round_trip_exactly(self):
        by_edid = {w.edid: w for w in self.reparsed.records("WTHR")}
        for name, palette in self.palettes.items():
            record = by_edid[f"EW{name.capitalize()}"]
            view = WeatherView.from_record(record)
            self.assertEqual(view.raw_colors, palette.raw_colors, name)
            self.assertEqual(view.fog, palette.fog, name)
            self.assertEqual(view.flags, palette.flags, name)

    def test_weathers_inherit_vanilla_family_structure(self):
        by_edid = {w.edid: w for w in self.reparsed.records("WTHR")}
        clear = by_edid["EWClear"]
        types = {s.type for s in clear.subrecords}
        # Cloud textures, image spaces, and directional ambient must be present.
        self.assertIn("IMSP", types)
        self.assertIn("DALC", types)
        self.assertEqual(len(clear.all("DALC")), 4)

    def test_climate_override_lists_our_weathers(self):
        import struct
        climates = self.reparsed.records("CLMT")
        self.assertEqual(len(climates), 1)
        clmt = climates[0]
        vanilla_clmt = next(c for c in self.vanilla.records("CLMT")
                            if c.edid == "SkyrimClimate")
        self.assertEqual(clmt.form_id, vanilla_clmt.form_id)  # true override

        wlst = clmt.first("WLST").data
        self.assertEqual(len(wlst), 7 * 12)
        weather_ids = {w.form_id for w in self.reparsed.records("WTHR")}
        total = 0
        for off in range(0, len(wlst), 12):
            fid, chance, _glob = struct.unpack_from("<IiI", wlst, off)
            self.assertIn(fid, weather_ids)
            total += chance
        self.assertEqual(total, 100)

    def test_cloud_layers_are_banded(self):
        # Lower cloud layers sit nearer the horizon light, upper layers
        # nearer the zenith: the two bands must not be painted identically.
        by_edid = {w.edid: w for w in self.reparsed.records("WTHR")}
        pnam = by_edid["EWClear"].first("PNAM").data
        self.assertEqual(len(pnam), 512)
        low_band = pnam[:16]     # layer 0, all four times
        high_band = pnam[16 * 16:16 * 16 + 16]  # layer 16
        self.assertNotEqual(low_band, high_band)

    def test_climate_keeps_vanilla_timing_and_textures(self):
        clmt = self.reparsed.records("CLMT")[0]
        vanilla_clmt = next(c for c in self.vanilla.records("CLMT")
                            if c.edid == "SkyrimClimate")
        self.assertEqual(clmt.first("TNAM").data, vanilla_clmt.first("TNAM").data)
        self.assertEqual(clmt.first("FNAM").data, vanilla_clmt.first("FNAM").data)


if __name__ == "__main__":
    unittest.main()
