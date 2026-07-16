"""elder-weathers command line.

  build   Generate EWWeathers.esp from the archetype model.
  show    Print the generated palette for one archetype.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .esp.reader import PluginReader
from .esp.weather import ColorType, TimeOfDay
from .esp.writer import build_weather_plugin
from .model.archetypes import ARCHETYPES
from .model.atmosphere import generate_palette
from .model.presets import export_presets


def _cmd_build(args: argparse.Namespace) -> int:
    esm = Path(args.skyrim_esm)
    if not esm.is_file():
        print(f"error: Skyrim.esm not found at {esm}", file=sys.stderr)
        return 2

    vanilla = PluginReader(esm)
    palettes = {name: generate_palette(a) for name, a in ARCHETYPES.items()}
    data = build_weather_plugin(palettes, vanilla)

    out = Path(args.out)
    out.write_bytes(data)

    reparsed = PluginReader(out)
    weathers = reparsed.records("WTHR")
    climates = reparsed.records("CLMT")
    regions = reparsed.records("REGN")
    print(f"{out.name}: {len(data)} bytes, {len(weathers)} weathers, "
          f"{len(climates)} climate override, {len(regions)} region overrides; "
          f"re-parse clean")
    return 0


def _cmd_export_presets(args: argparse.Namespace) -> int:
    palettes = {name: generate_palette(a) for name, a in ARCHETYPES.items()}
    written = export_presets(palettes, Path(args.out))
    print(f"{len(written)} workshop presets written to {args.out}")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    arch = ARCHETYPES.get(args.archetype)
    if arch is None:
        print(f"error: unknown archetype {args.archetype!r} "
              f"(have: {', '.join(ARCHETYPES)})", file=sys.stderr)
        return 2
    palette = generate_palette(arch)
    for ct in ColorType:
        row = "  ".join(
            f"{t.name.lower():7s} {palette.color(ct, t).r:3d},{palette.color(ct, t).g:3d},{palette.color(ct, t).b:3d}"
            for t in TimeOfDay)
        print(f"{ct.name:18s} {row}")
    f = palette.fog
    print(f"fog day {f.day_near:.0f}..{f.day_far:.0f}  night {f.night_near:.0f}..{f.night_far:.0f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="elder-weathers")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="generate the weather plugin")
    p_build.add_argument("--skyrim-esm", required=True,
                         help="path to a Skyrim Special Edition Skyrim.esm")
    p_build.add_argument("--out", default="EWWeathers.esp")
    p_build.set_defaults(func=_cmd_build)

    p_export = sub.add_parser(
        "export-presets",
        help="write SkyrimBridge weather-workshop presets for every archetype")
    p_export.add_argument("--out", default="WeatherPresets")
    p_export.set_defaults(func=_cmd_export_presets)

    p_show = sub.add_parser("show", help="print one archetype's palette")
    p_show.add_argument("archetype")
    p_show.set_defaults(func=_cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
