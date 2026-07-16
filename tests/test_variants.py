"""Variant roster: 19 weathers sampled from the model's parameter space.

Each variant must satisfy the family's physics and sit where its name
claims: a dense fog is nearer than a mist, a blizzard is darker and
windier than light snow, a violent storm is darker than the base storm.
"""

import unittest

from elder_weathers.esp.weather import ColorType, TimeOfDay
from elder_weathers.model.archetypes import (
    ARCHETYPES, FAMILY_OF, WEATHERS, edid_of, name_of_edid, split_family_chance)
from elder_weathers.model.atmosphere import generate_palette


class TestRoster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palettes = {name: generate_palette(a) for name, a in WEATHERS.items()}

    def sky(self, name, tod=TimeOfDay.DAY):
        return self.palettes[name].color(ColorType.SKY_UPPER, tod)

    def test_roster_size_and_families(self):
        self.assertEqual(len(WEATHERS), 19)
        for family in ARCHETYPES:
            self.assertIn(family, WEATHERS)          # base family is a weather
            self.assertEqual(FAMILY_OF[family], family)
        for name in WEATHERS:
            self.assertIn(FAMILY_OF[name], ARCHETYPES)

    def test_all_channels_in_range(self):
        for name, palette in self.palettes.items():
            for ct in ColorType:
                for tod in TimeOfDay:
                    c = palette.color(ct, tod)
                    for ch in (c.r, c.g, c.b, c.a):
                        self.assertTrue(0 <= ch <= 255, f"{name}/{ct.name}/{tod.name}")

    def test_fog_family_ordering(self):
        dense = WEATHERS["fog_dense"].fog_far
        base = WEATHERS["fog"].fog_far
        mist = WEATHERS["fog_mist"].fog_far
        self.assertLess(dense, base)
        self.assertLess(base, mist)

    def test_rain_family_ordering(self):
        light = self.sky("rain_light").luminance
        heavy = self.sky("rain_heavy").luminance
        self.assertLess(heavy, light)
        self.assertLess(WEATHERS["rain_heavy"].fog_far, WEATHERS["rain_light"].fog_far)

    def test_snow_blizzard_is_the_harsh_end(self):
        self.assertLess(WEATHERS["snow_blizzard"].fog_far, WEATHERS["snow_light"].fog_far)
        self.assertGreater(WEATHERS["snow_blizzard"].wind_speed,
                           WEATHERS["snow_light"].wind_speed)

    def test_storm_violent_darker_than_storm(self):
        self.assertLess(self.sky("storm_violent").luminance,
                        self.sky("storm").luminance)

    def test_clear_variants_spread(self):
        def spread(name):
            c = self.sky(name)
            return max(c.r, c.g, c.b) - min(c.r, c.g, c.b)
        self.assertLess(spread("clear_hazy"), spread("clear_crisp"))

    def test_cloudy_stars_track_cover(self):
        light = self.palettes["cloudy_light"].color(ColorType.STARS, TimeOfDay.NIGHT)
        heavy = self.palettes["cloudy_heavy"].color(ColorType.STARS, TimeOfDay.NIGHT)
        self.assertGreater(light.luminance, heavy.luminance)

    def test_flags_inherited_from_family(self):
        for name, arch in WEATHERS.items():
            self.assertEqual(arch.flags, ARCHETYPES[FAMILY_OF[name]].flags, name)

    def test_edid_mapping_round_trips(self):
        self.assertEqual(edid_of("clear_crisp"), "EWClearCrisp")
        self.assertEqual(edid_of("storm"), "EWStorm")
        for name in WEATHERS:
            self.assertEqual(name_of_edid(edid_of(name)), name)

    def test_chance_split_preserves_totals(self):
        for family in ARCHETYPES:
            for total in (5, 15, 30, 100):
                parts = split_family_chance(family, total)
                self.assertEqual(sum(c for _, c in parts), total, family)
                self.assertTrue(all(c >= 0 for _, c in parts))
                self.assertTrue(all(FAMILY_OF[n] == family for n, _ in parts))
        # The base weather carries the largest share of a 3-way family.
        parts = dict(split_family_chance("rain", 30))
        self.assertGreater(parts["rain"], parts["rain_light"])


if __name__ == "__main__":
    unittest.main()
