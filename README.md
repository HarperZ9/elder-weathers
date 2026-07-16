# elder-weathers

Original Skyrim weathers generated from an atmosphere model instead of
hand-tuned tables. One command produces `EWWeathers.esp`: seven authored
weather families, a climate override, and a full Tamriel region pass, as a
light (ESL-flagged) plugin.

```
python -m elder_weathers build --skyrim-esm "<path to Skyrim.esm>" --out EWWeathers.esp
python -m elder_weathers show clear
```

Standard library only; no dependencies to install. Run from the repository
root with `PYTHONPATH=src`, or install the package.

## How the colors are made

A compact single-scattering model (Rayleigh spectrum, Kasten-Young air mass,
turbidity-scaled Mie term) evaluates each archetype at four times of day and
fills the full 17-type weather color block, fog planes, cloud colors, and
directional ambient. Seven archetypes span the weather space: clear, cloudy,
overcast, rain, storm, fog, snow.

The model is tested by physical invariant, not by golden values: the day sky
must be blue-dominant, the sunrise zenith must stay blue while sunlight goes
warm, night must be far darker than day, overcast must collapse direct light,
fog must pull the far plane in. One measure of the model's grounding: its
clear-sunrise zenith lands within three points per channel of the vanilla
value Bethesda's artists tuned by hand, without ever reading it.

## What is authored and what is inherited

Every value the model speaks for is generated: the color block, fog, wind,
sun glare, classification flags, lightning color, cloud colors, directional
ambient. Structural fields the model does not yet cover (cloud texture paths,
layer alphas, precipitation and visual-effect references, sky statics, image
spaces) are inherited from the matching vanilla weather family by form
reference, the way any plugin references game content. There are no
third-party values anywhere in the output.

## The region pass

Skyrim distributes most of its weather through region records, so the plugin
overrides every Tamriel-worldspace distribution region (tundra, forests, the
Reach, coast, snow, marsh, and the rest) onto the authored weathers. Each
vanilla weather in a region's list is classified empirically (precipitation
flags, thunder bytes, fog planes, sky spectral spread) and its chance moves
to the matching archetype, so every region keeps its climate character: snowy
regions keep their snow share, rainy coasts keep their rain. FX regions,
scripted quest weathers, and non-Tamriel worldspaces are untouched byte for
byte; city worldspaces are a later pass.

## Scope, stated plainly

In-game visual validation is ahead of this tool: the gates prove format
correctness, physical coherence, and character preservation, not that it is
beautiful.

## Gates

| Suite | What it proves |
|---|---|
| `tests/test_esm_ground_truth.py` | The reader walks a real `Skyrim.esm` completely: compressed records, group recursion, 100+ weathers decoded |
| `tests/test_weather_decode.py` | Typed decoding agrees with vanilla ground truth, including older record forms |
| `tests/test_atmosphere_model.py` | Every generated palette satisfies the physical invariants |
| `tests/test_plugin_writer.py` | The built plugin re-parses byte-exact: colors, fog, flags, climate wiring, ESL-safe form IDs |

```
python -m unittest discover -s tests
```

Ground-truth suites skip cleanly when no `Skyrim.esm` is available; set
`ELDER_WEATHERS_SKYRIM_ESM` to point at one. Model and writer unit tests run
anywhere.

## Install

`EWWeathers.esp` is a normal light plugin: add it to your load order (as a
mod folder containing the .esp in Mod Organizer 2, or drop it in `Data/`).
It requires only Skyrim Special Edition.

## License

MIT. Copyright 2026 Zain Dana Harper.
