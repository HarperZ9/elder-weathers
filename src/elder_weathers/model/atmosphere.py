"""Single-scattering atmosphere model that generates weather palettes.

The model is a compact analytic approximation, not a path tracer:

- Rayleigh scattering with 1/lambda^4 channel weights gives the blue sky
  and the warm low-sun transmittance.
- Kasten-Young air mass lengthens the optical path at low sun elevations.
- A Mie term scaled by archetype turbidity adds forward haze and warmth.
- Cloud cover collapses direct light into isotropic scattered light and
  pulls the sky toward its own gray luminance.
- Night is the day sky rescaled to moonlight levels with a blue shift.

Every property the model must satisfy is asserted as a physical invariant
in tests/test_atmosphere_model.py; there are no golden color values.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

from ..esp.weather import Color, ColorType, FogDistances, TimeOfDay, WeatherView
from .archetypes import Archetype

# Rayleigh scattering weights for (680, 550, 440) nm, normalized to blue.
_RAYLEIGH = (0.175, 0.410, 1.0)

# Sun elevation (degrees) per time slot; night uses the moon.
_SUN_ELEVATION = {
    TimeOfDay.SUNRISE: 3.0,
    TimeOfDay.DAY: 45.0,
    TimeOfDay.SUNSET: 3.0,
    TimeOfDay.NIGHT: 40.0,   # moon elevation
}

_NIGHT_SCALE = 0.045        # moonlight vs daylight
_NIGHT_BLUE_SHIFT = (0.55, 0.75, 1.0)


def _air_mass(elevation_deg: float) -> float:
    """Kasten-Young relative optical air mass."""
    e = max(elevation_deg, 0.5)
    return 1.0 / (math.sin(math.radians(e)) + 0.50572 * (e + 6.07995) ** -1.6364)


def _transmittance(elevation_deg: float, turbidity: float) -> tuple[float, float, float]:
    """Direct-beam transmittance per channel (Rayleigh + Mie extinction)."""
    m = _air_mass(elevation_deg)
    mie = 0.025 * (turbidity - 1.0)
    return tuple(math.exp(-(0.20 * w + mie) * m) for w in _RAYLEIGH)


def _mix(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _luminance(c: tuple) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _desaturate(c: tuple, amount: float) -> tuple:
    gray = (_luminance(c),) * 3
    return _mix(c, gray, amount)


def _scale(c: tuple, s: float) -> tuple:
    return tuple(x * s for x in c)


class _SlotModel:
    """Linear-light colors for one archetype at one time slot."""

    def __init__(self, arch: Archetype, tod: TimeOfDay):
        elev = _SUN_ELEVATION[tod]
        trans = _transmittance(elev, arch.turbidity)
        night = tod == TimeOfDay.NIGHT

        # Direct light: transmitted sun (or moon) color.
        sun = trans
        # Scattered light: the high sky is lit along many paths, most far
        # less attenuated than the horizon-grazing direct beam. Light the
        # Rayleigh spectrum with a blend of the actual transmittance and a
        # high-sun reference, so the zenith stays blue at sunrise while the
        # horizon (which mixes toward the direct beam below) goes warm.
        sky_beam = _mix(_transmittance(45.0, arch.turbidity), sun, 0.35)
        sky_gain = 0.35 + 0.65 * math.sin(math.radians(max(elev, 0.0)))
        zenith = tuple(w * t * sky_gain for w, t in zip(_RAYLEIGH, sky_beam))
        horizon = _desaturate(_mix(zenith, sun, 0.55), 0.25)

        # Cloud cover collapses direct into isotropic scatter.
        cover = arch.cloud_cover
        ambient_gain = 1.0 - 0.55 * cover
        direct = _scale(sun, (1.0 - 0.92 * cover))
        zenith = _desaturate(_mix(zenith, _scale(horizon, 0.9), 0.7 * cover), arch.desaturation)
        horizon = _desaturate(horizon, arch.desaturation)

        dark = 1.0 - arch.darkening
        if night:
            zenith = _scale(tuple(z * b for z, b in zip(zenith, _NIGHT_BLUE_SHIFT)), _NIGHT_SCALE)
            horizon = _scale(tuple(h * b for h, b in zip(horizon, _NIGHT_BLUE_SHIFT)), _NIGHT_SCALE * 1.4)
            direct = _scale(tuple(d * b for d, b in zip(direct, _NIGHT_BLUE_SHIFT)), _NIGHT_SCALE * 2.2)

        self.zenith = _scale(zenith, dark)
        self.horizon = _scale(horizon, dark)
        self.direct = _scale(direct, dark)
        self.ambient = _scale(_mix(self.zenith, self.horizon, 0.5), ambient_gain * 0.8)
        self.night = night


def _to_color(linear: tuple, exposure: float = 255.0, gamma: float = 1.0 / 2.2) -> Color:
    channels = []
    for x in linear:
        v = int(round(max(0.0, x) ** gamma * exposure))
        channels.append(min(255, max(0, v)))
    return Color(channels[0], channels[1], channels[2], 255)


def _star_color(arch: Archetype, night: bool) -> Color:
    """Stars are emissive points occluded by cloud cover: their display
    value scales linearly with the visible fraction, after tone mapping."""
    if not night:
        return Color(0, 0, 0, 255)
    full = _to_color((0.35, 0.35, 0.35)).r
    v = int(round(full * arch.star_visibility))
    return Color(v, v, v, 255)


def _slot_colors(arch: Archetype, tod: TimeOfDay) -> dict[ColorType, Color]:
    m = _SlotModel(arch, tod)
    return {
        ColorType.SKY_UPPER: _to_color(m.zenith),
        ColorType.FOG_NEAR: _to_color(_desaturate(m.horizon, 0.4)),
        ColorType.CLOUD_LAYER_LOWER: _to_color(_mix(m.horizon, m.direct, 0.3)),
        ColorType.AMBIENT: _to_color(m.ambient),
        ColorType.SUNLIGHT: _to_color(m.direct),
        ColorType.SUN: _to_color(_scale(m.direct, 1.6)),
        ColorType.STARS: _star_color(arch, m.night),
        ColorType.SKY_LOWER: _to_color(_mix(m.zenith, m.horizon, 0.6)),
        ColorType.HORIZON: _to_color(m.horizon),
        ColorType.EFFECT_LIGHTING: _to_color(m.ambient),
        ColorType.CLOUD_LOD_DIFFUSE: _to_color(_mix(m.horizon, m.direct, 0.5)),
        ColorType.CLOUD_LOD_AMBIENT: _to_color(_scale(m.ambient, 0.8)),
        ColorType.FOG_FAR: _to_color(_desaturate(m.horizon, 0.6)),
        ColorType.SKY_STATICS: _to_color(m.horizon),
        ColorType.WATER_MULTIPLIER: _to_color(_scale(m.zenith, 0.6)),
        ColorType.SUN_GLARE: _to_color(_scale(m.direct, 1.3)),
        ColorType.MOON_GLARE: _to_color(_scale(m.zenith, 0.5) if not m.night
                                        else _scale(m.direct, 0.8)),
    }


def generate_palette(arch: Archetype) -> WeatherView:
    """Generate a full weather palette as a WeatherView.

    Returning the same type the reader produces keeps generated palettes and
    vanilla records interchangeable for the writer and for comparisons.
    """
    raw = bytearray()
    for ct in ColorType:
        for tod in TimeOfDay:
            c = _slot_colors(arch, tod)[ct]
            raw += bytes((c.r, c.g, c.b, c.a))

    # Quantize through float32: the plugin format stores f32, and palettes
    # must compare equal after a file round trip.
    fog_values = struct.unpack("<8f", struct.pack(
        "<8f", arch.fog_near, arch.fog_far,
        arch.fog_near * 0.85, arch.fog_far * 0.6,
        arch.fog_pow, arch.fog_pow, 0.9, 0.9))
    fog = FogDistances(*fog_values)

    data = bytearray(19)
    data[0] = arch.wind_speed
    data[3] = 32                  # trans delta
    data[4] = 64 if arch.cloud_cover < 0.5 else 16   # sun glare
    data[11] = arch.flags
    data[12], data[13], data[14] = 160, 160, 192      # lightning color

    return WeatherView(
        edid=arch.name,
        form_id=0,
        raw_colors=bytes(raw),
        fog=fog,
        data=bytes(data),
    )
