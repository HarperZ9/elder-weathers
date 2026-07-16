"""Weather archetypes: the model inputs for each authored weather family.

Each archetype is a small set of physical knobs. The atmosphere model turns
them into a full 17-type x 4-time color block plus fog and classification.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    wind_speed: int = 32  # 0..255


ARCHETYPES: dict[str, Archetype] = {
    "clear": Archetype(
        "clear", turbidity=2.0, cloud_cover=0.05, darkening=0.0,
        desaturation=0.0, fog_near=1400.0, fog_far=90000.0,
        flags=FLAG_PLEASANT, wind_speed=24),
    "cloudy": Archetype(
        "cloudy", turbidity=3.0, cloud_cover=0.45, darkening=0.05,
        desaturation=0.2, fog_near=1200.0, fog_far=60000.0,
        flags=FLAG_CLOUDY, wind_speed=48),
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
        flags=FLAG_CLOUDY, wind_speed=8),
    "snow": Archetype(
        "snow", turbidity=3.5, cloud_cover=0.9, darkening=0.08,
        desaturation=0.9, fog_near=900.0, fog_far=26000.0,
        flags=FLAG_SNOW | FLAG_CLOUDY, wind_speed=72),
}
