"""Import a workshop preset back into the model's terms.

Direct knobs (fog planes and power, wind, flags, star visibility) invert
exactly. The scattering knobs (turbidity, cloud cover, darkening,
desaturation) are recovered by fitting the model to the preset's colors:
coarse grid then two refinement rounds, objective = mean absolute channel
error across the full color block. The residual is reported honestly; a
large residual means the tuning left the space this model can express, and
the preset itself remains the artifact of record for it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ..esp.weather import Color, ColorType, FogDistances, TimeOfDay, WeatherView
from .archetypes import WEATHERS, Archetype, name_of_edid
from .atmosphere import generate_palette, _to_color
from .presets import COLOR_TYPE_NAMES, TOD_NAMES

_NAME_TO_TYPE = {v: k for k, v in COLOR_TYPE_NAMES.items()}
_NAME_TO_TOD = {v: k for k, v in TOD_NAMES.items()}


@dataclass(frozen=True)
class ImportResult:
    archetype: Archetype
    residual_mean: float   # mean absolute channel error, 0-255 scale
    residual_max: float


def _parse_sections(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line[0] in ";#":
            continue
        if line.startswith("["):
            current = sections.setdefault(line.strip("[]"), {})
            continue
        if "=" in line and current is not None:
            key, val = line.split("=", 1)
            current[key.strip()] = val.strip()
    return sections


def _colors_from(sections: dict) -> dict[tuple[ColorType, TimeOfDay], Color]:
    out: dict[tuple[ColorType, TimeOfDay], Color] = {}
    for key, val in sections.get("Colors", {}).items():
        base, _, tod_name = key.rpartition("_")
        if base not in _NAME_TO_TYPE or tod_name not in _NAME_TO_TOD:
            continue
        parts = [float(x) for x in val.split(",")]
        r, g, b = (int(round(max(0.0, min(1.0, p)) * 255)) for p in parts[:3])
        a = int(round(max(0.0, min(1.0, parts[3])) * 255)) if len(parts) > 3 else 255
        out[(_NAME_TO_TYPE[base], _NAME_TO_TOD[tod_name])] = Color(r, g, b, a)
    return out


def _color_error(candidate: Archetype,
                 target: dict[tuple[ColorType, TimeOfDay], Color]) -> float:
    palette = generate_palette(candidate)
    total, n = 0.0, 0
    for (ct, tod), want in target.items():
        got = palette.color(ct, tod)
        total += abs(got.r - want.r) + abs(got.g - want.g) + abs(got.b - want.b)
        n += 3
    return total / max(n, 1)


def _fit_scattering(base: Archetype,
                    target: dict[tuple[ColorType, TimeOfDay], Color]) -> Archetype:
    """Grid fit of (turbidity, cloud_cover, darkening, desaturation)."""
    ranges = {
        "turbidity": (1.0, 8.0),
        "cloud_cover": (0.0, 1.0),
        "darkening": (0.0, 0.6),
        "desaturation": (0.0, 1.0),
    }
    centers = {k: getattr(base, k) for k in ranges}
    spans = {k: (hi - lo) / 2 for k, (lo, hi) in ranges.items()}

    best = replace(base)
    best_err = _color_error(best, target)

    for _round in range(3):
        for key, (lo, hi) in ranges.items():
            span = spans[key]
            candidates = []
            for step in (-1.0, -0.5, 0.0, 0.5, 1.0):
                v = max(lo, min(hi, centers[key] + step * span))
                candidates.append(v)
            for v in sorted(set(candidates)):
                trial = replace(best, **{key: v})
                err = _color_error(trial, target)
                if err < best_err:
                    best, best_err = trial, err
                    centers[key] = v
        spans = {k: s * 0.35 for k, s in spans.items()}

    return best


def import_preset(path: Path | str,
                  archetype_name: str | None = None) -> ImportResult:
    path = Path(path)
    sections = _parse_sections(path)

    if archetype_name is None:
        edid = sections.get("Identity", {}).get("EditorID", path.stem)
        archetype_name = name_of_edid(edid) or edid.lower()
    base = WEATHERS.get(archetype_name, WEATHERS["clear"])

    # ── Direct knobs ─────────────────────────────────────────────────────
    fog = sections.get("Fog", {})
    wd = sections.get("WeatherData", {})

    def fnum(table: dict, key: str, fallback: float) -> float:
        try:
            return float(table[key])
        except (KeyError, ValueError):
            return fallback

    direct = replace(
        base,
        fog_near=fnum(fog, "DayNear", base.fog_near),
        fog_far=fnum(fog, "DayFar", base.fog_far),
        fog_pow=fnum(fog, "DayPower", base.fog_pow),
        wind_speed=int(round(fnum(wd, "WindSpeed", base.wind_speed / 255.0) * 255)),
        flags=int(fnum(wd, "Flags", base.flags)),
    )

    colors = _colors_from(sections)

    # Star visibility inverts exactly: display value scales linearly with
    # the visible fraction after tone mapping.
    star_key = (ColorType.STARS, TimeOfDay.NIGHT)
    if star_key in colors:
        full = _to_color((0.35, 0.35, 0.35)).r
        direct = replace(direct, star_visibility=min(1.0, colors[star_key].r / full))

    # ── Scattering knobs by fit ──────────────────────────────────────────
    fitted = _fit_scattering(direct, colors) if colors else direct

    # ── Residual, honestly ───────────────────────────────────────────────
    palette = generate_palette(fitted)
    diffs = [
        d
        for (ct, tod), want in colors.items()
        for got in (palette.color(ct, tod),)
        for d in (abs(got.r - want.r), abs(got.g - want.g), abs(got.b - want.b))
    ]
    mean = sum(diffs) / len(diffs) if diffs else 0.0
    peak = max(diffs) if diffs else 0.0

    return ImportResult(
        archetype=replace(fitted, name=archetype_name),
        residual_mean=mean,
        residual_max=peak,
    )
