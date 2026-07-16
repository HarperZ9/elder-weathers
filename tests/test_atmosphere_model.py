"""Physical-property tests for the palette model.

No golden values: every assertion is a physical invariant the generated
palette must satisfy. Runs everywhere (no game data required).
"""

import unittest

from elder_weathers.model.atmosphere import generate_palette
from elder_weathers.model.archetypes import ARCHETYPES
from elder_weathers.esp.weather import ColorType, TimeOfDay


class TestPalettePhysics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palettes = {name: generate_palette(a) for name, a in ARCHETYPES.items()}

    def color(self, arch, ct, tod):
        return self.palettes[arch].color(ct, tod)

    def test_all_archetypes_present(self):
        for name in ("clear", "cloudy", "overcast", "rain", "storm", "fog", "snow"):
            self.assertIn(name, self.palettes)

    def test_channels_in_range(self):
        for name, palette in self.palettes.items():
            for ct in ColorType:
                for tod in TimeOfDay:
                    c = palette.color(ct, tod)
                    for ch in (c.r, c.g, c.b, c.a):
                        self.assertTrue(0 <= ch <= 255, f"{name}/{ct.name}/{tod.name}: {c}")

    def test_clear_day_sky_blue_dominant(self):
        sky = self.color("clear", ColorType.SKY_UPPER, TimeOfDay.DAY)
        self.assertGreater(sky.b, sky.r)

    def test_clear_sunrise_zenith_stays_blue(self):
        # The high sky is lit along many paths, most far less attenuated
        # than the horizon-grazing direct beam: the zenith stays blue at
        # sunrise (vanilla ground truth agrees: 66,90,121).
        sky = self.color("clear", ColorType.SKY_UPPER, TimeOfDay.SUNRISE)
        self.assertGreater(sky.b, sky.r)

    def test_clear_sunrise_sunlight_warm(self):
        sun = self.color("clear", ColorType.SUNLIGHT, TimeOfDay.SUNRISE)
        self.assertGreater(sun.r, sun.b)

    def test_clear_daylight_brightness_ordering(self):
        lum = {t: self.color("clear", ColorType.SKY_UPPER, t).luminance for t in TimeOfDay}
        self.assertLess(lum[TimeOfDay.NIGHT], lum[TimeOfDay.SUNRISE])
        self.assertLess(lum[TimeOfDay.SUNRISE], lum[TimeOfDay.DAY])
        self.assertLess(lum[TimeOfDay.SUNSET], lum[TimeOfDay.DAY])

    def test_night_much_darker_than_day(self):
        day = self.color("clear", ColorType.SKY_UPPER, TimeOfDay.DAY).luminance
        night = self.color("clear", ColorType.SKY_UPPER, TimeOfDay.NIGHT).luminance
        self.assertLess(night, day * 0.25)

    def test_overcast_flattens_direct_light(self):
        clear_sun = self.color("clear", ColorType.SUNLIGHT, TimeOfDay.DAY).luminance
        over_sun = self.color("overcast", ColorType.SUNLIGHT, TimeOfDay.DAY).luminance
        self.assertLess(over_sun, clear_sun * 0.6)

    def test_overcast_sky_desaturated(self):
        sky = self.color("overcast", ColorType.SKY_UPPER, TimeOfDay.DAY)
        spread = max(sky.r, sky.g, sky.b) - min(sky.r, sky.g, sky.b)
        clear = self.color("clear", ColorType.SKY_UPPER, TimeOfDay.DAY)
        clear_spread = max(clear.r, clear.g, clear.b) - min(clear.r, clear.g, clear.b)
        self.assertLess(spread, clear_spread * 0.5)

    def test_storm_darker_than_cloudy(self):
        cloudy = self.color("cloudy", ColorType.SKY_UPPER, TimeOfDay.DAY).luminance
        storm = self.color("storm", ColorType.SKY_UPPER, TimeOfDay.DAY).luminance
        self.assertLess(storm, cloudy)

    def test_fog_distances_relational(self):
        clear = self.palettes["clear"].fog
        fog = self.palettes["fog"].fog
        storm = self.palettes["storm"].fog
        self.assertLess(fog.day_far, clear.day_far * 0.25)
        self.assertLess(storm.day_far, clear.day_far)
        for p in self.palettes.values():
            self.assertGreater(p.fog.day_far, p.fog.day_near)
            self.assertGreater(p.fog.night_far, p.fog.night_near)

    def test_snow_bright_and_desaturated(self):
        snow = self.color("snow", ColorType.SKY_UPPER, TimeOfDay.DAY)
        spread = max(snow.r, snow.g, snow.b) - min(snow.r, snow.g, snow.b)
        self.assertLess(spread, 30)
        storm = self.color("storm", ColorType.SKY_UPPER, TimeOfDay.DAY)
        self.assertGreater(snow.luminance, storm.luminance)

    def test_classification_flags(self):
        self.assertTrue(self.palettes["clear"].is_pleasant)
        self.assertTrue(self.palettes["rain"].is_rainy)
        self.assertTrue(self.palettes["storm"].is_rainy)
        self.assertTrue(self.palettes["snow"].is_snow)
        self.assertTrue(self.palettes["overcast"].is_cloudy)


if __name__ == "__main__":
    unittest.main()
