"""The preset exporter must emit WeatherEditor-compatible INIs whose values
round-trip exactly to the palette (normalized to the editor's [0,1] floats).

Only model-owned sections are emitted ([Colors], [Fog], [WeatherData],
[DirectionalAmbient]): the editor overlays presets onto the captured live
weather, so omitted sections keep their in-game values by design.
"""

import unittest
from pathlib import Path
import tempfile

from elder_weathers.esp.weather import ColorType, TimeOfDay
from elder_weathers.model.archetypes import ARCHETYPES, WEATHERS, edid_of
from elder_weathers.model.atmosphere import generate_palette
from elder_weathers.model.presets import export_presets, COLOR_TYPE_NAMES, TOD_NAMES


def parse_preset(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current = None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if line.startswith("["):
            current = line.strip("[]")
            sections[current] = {}
            continue
        if "=" in line and current is not None:
            key, val = line.split("=", 1)
            sections[current][key.strip()] = val.strip()
    return sections


class TestPresetExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palettes = {name: generate_palette(a) for name, a in WEATHERS.items()}
        cls.dir = Path(tempfile.mkdtemp())
        cls.written = export_presets(cls.palettes, cls.dir)
        cls.presets = {p.stem: parse_preset(p) for p in cls.written}

    def test_one_preset_per_weather_named_by_editor_id(self):
        self.assertEqual(len(self.written), len(WEATHERS))
        for name in WEATHERS:
            self.assertIn(edid_of(name), self.presets)

    def test_only_model_owned_sections(self):
        for name, sections in self.presets.items():
            self.assertEqual(
                set(sections),
                {"Identity", "Colors", "Fog", "WeatherData", "DirectionalAmbient"},
                name)

    def test_colors_round_trip_normalized(self):
        palette = self.palettes["clear"]
        colors = self.presets["EWClear"]["Colors"]
        for ct in ColorType:
            for tod in TimeOfDay:
                key = f"{COLOR_TYPE_NAMES[ct]}_{TOD_NAMES[tod]}"
                self.assertIn(key, colors, key)
                r, g, b, a = (float(x) for x in colors[key].split(","))
                c = palette.color(ct, tod)
                self.assertAlmostEqual(r, c.r / 255.0, places=5, msg=key)
                self.assertAlmostEqual(g, c.g / 255.0, places=5, msg=key)
                self.assertAlmostEqual(b, c.b / 255.0, places=5, msg=key)

    def test_fog_absolute_values(self):
        fog = self.presets["EWFog"]["Fog"]
        palette = self.palettes["fog"]
        self.assertAlmostEqual(float(fog["DayNear"]), palette.fog.day_near, places=2)
        self.assertAlmostEqual(float(fog["DayFar"]), palette.fog.day_far, places=2)
        self.assertAlmostEqual(float(fog["DayPower"]), palette.fog.day_pow, places=4)

    def test_weather_data_normalized(self):
        wd = self.presets["EWStorm"]["WeatherData"]
        palette = self.palettes["storm"]
        self.assertAlmostEqual(float(wd["WindSpeed"]), palette.data[0] / 255.0, places=5)
        self.assertAlmostEqual(float(wd["SunGlare"]), palette.data[4] / 255.0, places=5)
        self.assertEqual(int(wd["Flags"]), palette.flags)

    def test_directional_ambient_matches_esp_derivation(self):
        # Same derivation as the esp writer's DALC: X/Y at 1.0, Z+ lifted
        # 1.25, Z- dropped 0.6, specular 0.5.
        da = self.presets["EWClear"]["DirectionalAmbient"]
        a = self.palettes["clear"].color(ColorType.AMBIENT, TimeOfDay.DAY)
        zmax = [float(x) for x in da["ZMax_Day"].split(",")]
        self.assertAlmostEqual(zmax[0], min(255, int(a.r * 1.25)) / 255.0, places=5)
        xmax = [float(x) for x in da["XMax_Day"].split(",")]
        self.assertAlmostEqual(xmax[0], min(255, int(a.r * 1.0)) / 255.0, places=5)
        self.assertAlmostEqual(float(da["FresnelPower_Day"]), 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
