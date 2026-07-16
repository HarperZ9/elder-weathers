"""Typed WTHR decode, validated against vanilla ground truth."""

import unittest

from elder_weathers.esp.weather import ColorType, TimeOfDay, WeatherView
from tests.test_esm_ground_truth import ESM

if ESM is not None:
    from elder_weathers.esp.reader import PluginReader


@unittest.skipIf(ESM is None, "no Skyrim.esm available (set ELDER_WEATHERS_SKYRIM_ESM)")
class TestVanillaWeatherDecode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = PluginReader(ESM)
        cls.by_edid = {r.edid: r for r in cls.reader.records("WTHR")}

    def view(self, edid):
        return WeatherView.from_record(self.by_edid[edid])

    def test_clear_day_sky_is_blue_dominant(self):
        sky = self.view("SkyrimClear").color(ColorType.SKY_UPPER, TimeOfDay.DAY)
        self.assertGreater(sky.b, sky.r)

    def test_clear_night_sky_darker_than_day(self):
        v = self.view("SkyrimClear")
        day = v.color(ColorType.SKY_UPPER, TimeOfDay.DAY)
        night = v.color(ColorType.SKY_UPPER, TimeOfDay.NIGHT)
        self.assertLess(night.luminance, day.luminance * 0.25)

    def test_clear_sunrise_sunlight_is_warm(self):
        sun = self.view("SkyrimClear").color(ColorType.SUNLIGHT, TimeOfDay.SUNRISE)
        self.assertGreater(sun.r, sun.b)

    def test_fog_distances_sane(self):
        fog = self.view("SkyrimClear").fog
        self.assertGreater(fog.day_far, fog.day_near)
        self.assertGreater(fog.night_far, fog.night_near)
        self.assertGreater(fog.day_near, 0)

    def test_storm_fog_nearer_than_clear(self):
        clear = self.view("SkyrimClear").fog
        storm = self.view("SkyrimStormRain").fog
        self.assertLess(storm.day_far, clear.day_far)

    def test_weather_flags_classify(self):
        self.assertTrue(self.view("SkyrimClear").is_pleasant)
        self.assertTrue(self.view("SkyrimStormRain").is_rainy)
        self.assertTrue(self.view("SkyrimFog").is_cloudy or self.view("SkyrimFog").is_pleasant)

    def test_all_vanilla_weathers_decode(self):
        counts = set()
        for edid, record in self.by_edid.items():
            view = WeatherView.from_record(record)
            self.assertGreaterEqual(view.color_type_count, 13, edid)
            counts.add(view.color_type_count)
        # The modern 17-type form must dominate vanilla.
        self.assertIn(17, counts)


if __name__ == "__main__":
    unittest.main()
