"""Typed view over WTHR records.

Field layout follows the Skyrim Special Edition plugin format:
  NAM0  17 color types x 4 times of day x RGBA          (272 bytes)
  FNAM  8 fog floats                                     (32 bytes)
  DATA  19 bytes of weather data (wind, glare, flags, lightning color)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum

from .reader import Record


class ColorType(IntEnum):
    SKY_UPPER = 0
    FOG_NEAR = 1
    CLOUD_LAYER_LOWER = 2
    AMBIENT = 3
    SUNLIGHT = 4
    SUN = 5
    STARS = 6
    SKY_LOWER = 7
    HORIZON = 8
    EFFECT_LIGHTING = 9
    CLOUD_LOD_DIFFUSE = 10
    CLOUD_LOD_AMBIENT = 11
    FOG_FAR = 12
    SKY_STATICS = 13
    WATER_MULTIPLIER = 14
    SUN_GLARE = 15
    MOON_GLARE = 16


class TimeOfDay(IntEnum):
    SUNRISE = 0
    DAY = 1
    SUNSET = 2
    NIGHT = 3


# DATA byte 11 flags (weather classification)
FLAG_PLEASANT = 0x01
FLAG_CLOUDY = 0x02
FLAG_RAINY = 0x04
FLAG_SNOW = 0x08


@dataclass(frozen=True)
class Color:
    r: int
    g: int
    b: int
    a: int

    @property
    def luminance(self) -> float:
        return 0.2126 * self.r + 0.7152 * self.g + 0.0722 * self.b


@dataclass(frozen=True)
class FogDistances:
    day_near: float
    day_far: float
    night_near: float
    night_far: float
    day_pow: float
    night_pow: float
    day_max: float
    night_max: float


@dataclass(frozen=True)
class WeatherView:
    edid: str | None
    form_id: int
    raw_colors: bytes
    fog: FogDistances
    data: bytes

    @classmethod
    def from_record(cls, record: Record) -> "WeatherView":
        nam0 = record.first("NAM0")
        fnam = record.first("FNAM")
        data = record.first("DATA")
        if nam0 is None or fnam is None or data is None:
            raise ValueError(f"WTHR {record.edid or record.form_id:X} missing NAM0/FNAM/DATA")
        # One 16-byte row per color type (4 times x RGBA). Current records
        # carry 17 types (272 bytes); older form versions observed in vanilla
        # carry 13 or 14. Anything below 13 or misaligned is malformed.
        size = len(nam0.data)
        if size % 16 != 0 or size < 13 * 16:
            raise ValueError(f"malformed NAM0 ({size} bytes) in {record.edid}")
        return cls(
            edid=record.edid,
            form_id=record.form_id,
            raw_colors=nam0.data,
            fog=FogDistances(*struct.unpack("<8f", fnam.data)),
            data=data.data,
        )

    @property
    def color_type_count(self) -> int:
        return len(self.raw_colors) // 16

    def color(self, color_type: ColorType, time: TimeOfDay) -> Color:
        if int(color_type) >= self.color_type_count:
            raise IndexError(
                f"{self.edid}: color type {color_type.name} absent "
                f"(record carries {self.color_type_count} types)")
        offset = (int(color_type) * 4 + int(time)) * 4
        r, g, b, a = self.raw_colors[offset:offset + 4]
        return Color(r, g, b, a)

    @property
    def flags(self) -> int:
        return self.data[11]

    @property
    def is_pleasant(self) -> bool:
        return bool(self.flags & FLAG_PLEASANT)

    @property
    def is_cloudy(self) -> bool:
        return bool(self.flags & FLAG_CLOUDY)

    @property
    def is_rainy(self) -> bool:
        return bool(self.flags & FLAG_RAINY)

    @property
    def is_snow(self) -> bool:
        return bool(self.flags & FLAG_SNOW)
