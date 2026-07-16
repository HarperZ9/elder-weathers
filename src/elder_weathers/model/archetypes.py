"""Weather archetypes: the model inputs for each authored weather family.

Each archetype is a small set of physical knobs. The atmosphere model turns
them into a full 17-type x 4-time color block plus fog and classification.

ARCHETYPES holds the seven base families. WEATHERS is the full shipped
roster: every family plus its variants, each a full Archetype sampled from
the same parameter space (a dense fog is the fog family with the planes
pulled in, a blizzard is snow with wind and darkening raised). FAMILY_OF
maps any weather back to its family for classification and templates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..esp.weather import FLAG_CLOUDY, FLAG_PLEASANT, FLAG_RAINY, FLAG_SNOW


@dataclass(frozen=True)
class Archetype:
    name: str
    turbidity: float      # aerosol load; raises Mie scattering and warmth
    cloud_cover: float    # 0 clear .. 1 full overcast
    darkening: float      # additional broadband attenuation (storm cells)
    desaturation: float   # 0 spectral .. 1 gray (precipitation, haze)
    fog_near: float       # daytime near fog plane, game units
    fog_far: float        # daytime far fog plane, game units
    flags: int
    wind_speed: int = 32       # 0..255
    star_visibility: float = 0.0  # 0 hidden .. 1 full night sky
    fog_pow: float = 0.4       # lower = density piles at the near plane


ARCHETYPES: dict[str, Archetype] = {
    "clear": Archetype(
        "clear", turbidity=2.0, cloud_cover=0.05, darkening=0.0,
        desaturation=0.0, fog_near=1400.0, fog_far=90000.0,
        flags=FLAG_PLEASANT, wind_speed=24, star_visibility=1.0),
    "cloudy": Archetype(
        "cloudy", turbidity=3.0, cloud_cover=0.45, darkening=0.05,
        desaturation=0.2, fog_near=1200.0, fog_far=60000.0,
        flags=FLAG_CLOUDY, wind_speed=48, star_visibility=0.45),
    "overcast": Archetype(
        "overcast", turbidity=4.0, cloud_cover=0.95, darkening=0.12,
        desaturation=0.7, fog_near=1000.0, fog_far=42000.0,
        flags=FLAG_CLOUDY, wind_speed=56),
    "rain": Archetype(
        "rain", turbidity=5.0, cloud_cover=0.95, darkening=0.25,
        desaturation=0.65, fog_near=800.0, fog_far=30000.0,
        flags=FLAG_RAINY | FLAG_CLOUDY, wind_speed=88),
    "storm": Archetype(
        "storm", turbidity=6.0, cloud_cover=1.0, darkening=0.45,
        desaturation=0.6, fog_near=600.0, fog_far=20000.0,
        flags=FLAG_RAINY | FLAG_CLOUDY, wind_speed=160),
    "fog": Archetype(
        "fog", turbidity=7.0, cloud_cover=0.8, darkening=0.10,
        desaturation=0.85, fog_near=250.0, fog_far=9000.0,
        flags=FLAG_CLOUDY, wind_speed=8, fog_pow=0.22),
    "snow": Archetype(
        "snow", turbidity=3.5, cloud_cover=0.9, darkening=0.08,
        desaturation=0.9, fog_near=900.0, fog_far=26000.0,
        flags=FLAG_SNOW | FLAG_CLOUDY, wind_speed=72),
}

# ── Variants: knob deltas over a family ─────────────────────────────────────
# (family, overrides). Flags always inherit from the family.
_VARIANTS: dict[str, tuple[str, dict]] = {
    "clear_crisp": ("clear", dict(
        turbidity=1.3, wind_speed=16)),
    "clear_hazy": ("clear", dict(
        turbidity=3.8, desaturation=0.15, fog_far=70000.0, star_visibility=0.8)),
    "cloudy_light": ("cloudy", dict(
        cloud_cover=0.3, turbidity=2.5, star_visibility=0.6, wind_speed=32)),
    "cloudy_heavy": ("cloudy", dict(
        cloud_cover=0.65, darkening=0.08, desaturation=0.35,
        star_visibility=0.2, wind_speed=64)),
    "overcast_bright": ("overcast", dict(
        darkening=0.05, desaturation=0.6, cloud_cover=0.9)),
    "rain_light": ("rain", dict(
        darkening=0.15, fog_far=40000.0, wind_speed=64)),
    "rain_heavy": ("rain", dict(
        darkening=0.34, fog_near=600.0, fog_far=20000.0, wind_speed=128)),
    "storm_violent": ("storm", dict(
        darkening=0.55, fog_near=450.0, fog_far=14000.0, wind_speed=220)),
    "fog_mist": ("fog", dict(
        fog_near=500.0, fog_far=16000.0, desaturation=0.7, fog_pow=0.3)),
    "fog_dense": ("fog", dict(
        fog_near=140.0, fog_far=5000.0, fog_pow=0.18, darkening=0.15)),
    "snow_light": ("snow", dict(
        darkening=0.04, fog_near=1200.0, fog_far=34000.0,
        wind_speed=40, desaturation=0.85)),
    "snow_blizzard": ("snow", dict(
        darkening=0.22, fog_near=350.0, fog_far=9000.0,
        wind_speed=210, desaturation=0.95, fog_pow=0.28)),
}

# ── The shipped roster ───────────────────────────────────────────────────────
WEATHERS: dict[str, Archetype] = dict(ARCHETYPES)
FAMILY_OF: dict[str, str] = {name: name for name in ARCHETYPES}
for _name, (_family, _delta) in _VARIANTS.items():
    WEATHERS[_name] = replace(ARCHETYPES[_family], name=_name, **_delta)
    FAMILY_OF[_name] = _family


def edid_of(name: str) -> str:
    """clear_crisp -> EWClearCrisp"""
    return "EW" + "".join(part.capitalize() for part in name.split("_"))


_NAME_BY_EDID = {edid_of(n): n for n in WEATHERS}


def name_of_edid(edid: str) -> str | None:
    return _NAME_BY_EDID.get(edid)


# Within a family, the base weather carries the dominant share.
_BASE_WEIGHT, _VARIANT_WEIGHT = 3, 1


def split_family_chance(family: str, total: int) -> list[tuple[str, int]]:
    """Split a family's chance across its variants, preserving the integer
    total exactly (largest-remainder method), base weather first."""
    members = [family] + sorted(
        n for n, f in FAMILY_OF.items() if f == family and n != family)
    weights = [_BASE_WEIGHT] + [_VARIANT_WEIGHT] * (len(members) - 1)
    weight_sum = sum(weights)

    raw = [total * w / weight_sum for w in weights]
    floors = [int(r) for r in raw]
    shortfall = total - sum(floors)
    order = sorted(range(len(members)), key=lambda i: raw[i] - floors[i],
                   reverse=True)
    for i in order[:shortfall]:
        floors[i] += 1
    return [(members[i], floors[i]) for i in range(len(members))]
