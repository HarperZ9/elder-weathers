"""import-preset: recover archetype knobs from a workshop preset.

The criterion is palette reproduction, not parameter identity: importing an
untouched export must regenerate the original palette almost exactly, and a
hand-tuned preset must surface its changes in the fit and the residual.
"""

import unittest
from pathlib import Path
import tempfile

from elder_weathers.esp.weather import ColorType, TimeOfDay
from elder_weathers.model.archetypes import ARCHETYPES
from elder_weathers.model.atmosphere import generate_palette
from elder_weathers.model.presets import export_presets
from elder_weathers.model.import_preset import import_preset


class TestImportRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palettes = {name: generate_palette(a) for name, a in ARCHETYPES.items()}
        cls.dir = Path(tempfile.mkdtemp())
        cls.paths = {p.stem: p for p in export_presets(cls.palettes, cls.dir)}

    def test_direct_fields_recovered_exactly(self):
        for name, arch in ARCHETYPES.items():
            result = import_preset(self.paths[f"EW{name.capitalize()}"])
            fitted = result.archetype
            self.assertAlmostEqual(fitted.fog_near, arch.fog_near, delta=1.0, msg=name)
            self.assertAlmostEqual(fitted.fog_far, arch.fog_far, delta=1.0, msg=name)
            self.assertAlmostEqual(fitted.fog_pow, arch.fog_pow, places=3, msg=name)
            self.assertEqual(fitted.wind_speed, arch.wind_speed, name)
            self.assertEqual(fitted.flags, arch.flags, name)
            self.assertAlmostEqual(fitted.star_visibility, arch.star_visibility,
                                   delta=0.05, msg=name)

    def test_palette_reproduction_within_quantization(self):
        # Regenerating from the fitted archetype must land close to the
        # original palette: mean channel error small, max bounded.
        for name in ARCHETYPES:
            result = import_preset(self.paths[f"EW{name.capitalize()}"])
            regen = generate_palette(result.archetype)
            original = self.palettes[name]
            diffs = []
            for ct in ColorType:
                for tod in TimeOfDay:
                    a, b = regen.color(ct, tod), original.color(ct, tod)
                    diffs += [abs(a.r - b.r), abs(a.g - b.g), abs(a.b - b.b)]
            mean = sum(diffs) / len(diffs)
            self.assertLess(mean, 3.0, f"{name}: mean channel error {mean:.2f}")
            self.assertLess(max(diffs), 16, f"{name}: max channel error {max(diffs)}")
            self.assertLess(result.residual_mean, 3.0, name)

    def test_tuned_preset_surfaces_changes(self):
        # Hand-edit the exported clear preset: pull fog in hard.
        text = self.paths["EWClear"].read_text()
        text = text.replace("DayFar = 90000", "DayFar = 30000")
        tuned = self.dir / "EWClear_tuned.ini"
        tuned.write_text(text)

        result = import_preset(tuned, archetype_name="clear")
        self.assertAlmostEqual(result.archetype.fog_far, 30000.0, delta=1.0)
        # The unchanged colors still fit the clear knobs.
        self.assertLess(result.residual_mean, 4.0)

    def test_unknown_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            import_preset(self.dir / "nope.ini")


if __name__ == "__main__":
    unittest.main()
