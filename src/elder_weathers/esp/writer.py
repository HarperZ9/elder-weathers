"""Light-plugin writer: authored weathers plus a climate override.

Authoring policy, stated plainly:

- Every value the atmosphere model speaks for (the 17x4 color block, fog,
  wind, glare, classification flags, lightning, cloud colors, directional
  ambient) is OURS, generated from the archetype model.
- Structural fields the model does not yet speak for (cloud texture paths,
  layer alphas, precipitation and visual-effect references, sky statics,
  image spaces) are inherited from the matching vanilla weather family by
  form reference: the plugin references the game's own content, the way any
  plugin does. No third-party values anywhere.

The output is an ESL-flagged .esp with Skyrim.esm as its only master.
"""

from __future__ import annotations

import struct

from .reader import PluginReader, Record, FLAG_LIGHT
from .weather import ColorType, TimeOfDay, WeatherView

_RECORD_HEADER = struct.Struct("<4sIIIHHHH")
_GROUP_HEADER = struct.Struct("<4sI4siHHHH")

# Structural template per archetype: the vanilla family whose non-modeled
# fields (textures, alphas, precipitation references) each weather inherits.
TEMPLATE_FOR = {
    "clear": "SkyrimClear",
    "cloudy": "SkyrimCloudy",
    "overcast": "SkyrimCloudy",
    "rain": "SkyrimOvercastRain",
    "storm": "SkyrimStormRain",
    "fog": "SkyrimFog",
    "snow": "SkyrimOvercastSnow",
}

_CLIMATE_EDID = "SkyrimClimate"
_MODULE_INDEX = 0x01           # one master -> new records live at index 1
_FIRST_OBJECT_ID = 0x800       # ESL-safe object range start

# WLST chances per archetype (must sum to 100).
_CHANCES = {
    "clear": 30, "cloudy": 20, "overcast": 10,
    "rain": 15, "storm": 5, "fog": 10, "snow": 10,
}


def _pack_subrecord(sub_type: str, data: bytes) -> bytes:
    if len(data) > 0xFFFF:
        raise ValueError(f"subrecord {sub_type} too large ({len(data)})")
    return struct.pack("<4sH", sub_type.encode("ascii"), len(data)) + data


def _pack_record(record_type: str, flags: int, form_id: int, version: int,
                 subrecords: list[tuple[str, bytes]]) -> bytes:
    payload = b"".join(_pack_subrecord(t, d) for t, d in subrecords)
    header = _RECORD_HEADER.pack(
        record_type.encode("ascii"), len(payload), flags, form_id, 0, 0, version, 0)
    return header + payload


def _pack_group(label: str, records: bytes) -> bytes:
    header = _GROUP_HEADER.pack(
        b"GRUP", _GROUP_HEADER.size + len(records), label.encode("ascii"),
        0, 0, 0, 0, 0)
    return header + records


def _replace(subrecords: list[tuple[str, bytes]], sub_type: str,
             data: bytes) -> list[tuple[str, bytes]]:
    out, done = [], False
    for t, d in subrecords:
        if t == sub_type and not done:
            out.append((t, data))
            done = True
        else:
            out.append((t, d))
    if not done:
        raise ValueError(f"template lacks {sub_type} subrecord")
    return out


def _replace_all(subrecords: list[tuple[str, bytes]], sub_type: str,
                 blocks: list[bytes]) -> list[tuple[str, bytes]]:
    out, i = [], 0
    for t, d in subrecords:
        if t == sub_type:
            if i >= len(blocks):
                raise ValueError(f"more {sub_type} blocks in template than provided")
            out.append((t, blocks[i]))
            i += 1
        else:
            out.append((t, d))
    if i != len(blocks):
        raise ValueError(f"template has {i} {sub_type} blocks, provided {len(blocks)}")
    return out


def _merged_data(template: bytes, palette: WeatherView) -> bytes:
    """Template DATA with the model-owned bytes overwritten."""
    data = bytearray(template)
    data[0] = palette.data[0]                     # wind speed
    data[4] = palette.data[4]                     # sun glare
    data[11] = palette.data[11]                   # classification flags
    data[12:15] = palette.data[12:15]             # lightning color
    return bytes(data)


def _cloud_colors(palette: WeatherView) -> bytes:
    """PNAM: 32 layers x 4 times, uniform per time from the model."""
    per_time = [palette.color(ColorType.CLOUD_LOD_DIFFUSE, t) for t in TimeOfDay]
    row = b"".join(bytes((c.r, c.g, c.b, c.a)) for c in per_time)
    return row * 32


def _directional_ambient(palette: WeatherView, time: TimeOfDay) -> bytes:
    """DALC: X+/X-/Y+/Y- ambient, Z+ lifted, Z- dropped, spec, fresnel."""
    a = palette.color(ColorType.AMBIENT, time)

    def rgba(scale: float) -> bytes:
        return bytes((min(255, int(a.r * scale)), min(255, int(a.g * scale)),
                      min(255, int(a.b * scale)), 255))

    block = rgba(1.0) * 4 + rgba(1.25) + rgba(0.6)   # X+/X-/Y+/Y-/Z+/Z-
    block += rgba(0.5)                                # specular
    block += struct.pack("<f", 1.0)                   # fresnel power
    return block


def _build_weather(palette: WeatherView, template: Record, edid: str,
                   form_id: int) -> bytes:
    subs = [(s.type, s.data) for s in template.subrecords]
    subs = _replace(subs, "EDID", edid.encode("ascii") + b"\x00")
    subs = _replace(subs, "NAM0", palette.raw_colors)
    subs = _replace(subs, "FNAM", struct.pack(
        "<8f", palette.fog.day_near, palette.fog.day_far,
        palette.fog.night_near, palette.fog.night_far,
        palette.fog.day_pow, palette.fog.night_pow,
        palette.fog.day_max, palette.fog.night_max))
    subs = _replace(subs, "DATA", _merged_data(template.first("DATA").data, palette))
    subs = _replace(subs, "PNAM", _cloud_colors(palette))
    subs = _replace_all(subs, "DALC",
                        [_directional_ambient(palette, t) for t in TimeOfDay])
    return _pack_record("WTHR", 0, form_id, template.version, subs)


def _build_climate_override(vanilla_climate: Record,
                            weather_ids: dict[str, int]) -> bytes:
    entries = b""
    for name, form_id in weather_ids.items():
        entries += struct.pack("<IiI", form_id, _CHANCES[name], 0)
    subs = [(s.type, s.data) for s in vanilla_climate.subrecords]
    subs = _replace(subs, "WLST", entries)
    return _pack_record("CLMT", 0, vanilla_climate.form_id,
                        vanilla_climate.version, subs)


def build_weather_plugin(palettes: dict[str, WeatherView],
                         vanilla: PluginReader) -> bytes:
    """Build the ESL-flagged plugin from generated palettes and vanilla
    structural templates."""
    if set(palettes) != set(TEMPLATE_FOR):
        raise ValueError("palettes must cover exactly the known archetypes")
    if sum(_CHANCES.values()) != 100:
        raise ValueError("climate chances must sum to 100")

    by_edid = {r.edid: r for r in vanilla.records("WTHR")}
    vanilla_climate = next(c for c in vanilla.records("CLMT")
                           if c.edid == _CLIMATE_EDID)

    weather_ids: dict[str, int] = {}
    weather_records = b""
    for i, name in enumerate(sorted(palettes)):
        template = by_edid[TEMPLATE_FOR[name]]
        form_id = (_MODULE_INDEX << 24) | (_FIRST_OBJECT_ID + i)
        weather_ids[name] = form_id
        weather_records += _build_weather(
            palettes[name], template, f"EW{name.capitalize()}", form_id)

    climate_records = _build_climate_override(vanilla_climate, weather_ids)

    header_subs = [
        ("HEDR", struct.pack("<fII", 1.71, 10, _FIRST_OBJECT_ID + len(palettes))),
        ("CNAM", b"elder-weathers\x00"),
        ("MAST", b"Skyrim.esm\x00"),
        ("DATA", struct.pack("<Q", 0)),
    ]
    tes4 = _pack_record("TES4", FLAG_LIGHT, 0, 44, header_subs)

    return tes4 + _pack_group("CLMT", climate_records) + \
        _pack_group("WTHR", weather_records)
