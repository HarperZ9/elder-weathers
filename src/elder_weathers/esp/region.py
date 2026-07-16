"""Region pass: map vanilla weather regions onto the EW archetypes.

Classification is empirical, derived from the vanilla weathers themselves
(flags, thunder bytes, fog planes, day-sky channel spread), so a region's
climate character survives the swap: snow shares stay snow, rain stays rain.

Scope: Tamriel-worldspace distribution regions only. FX regions (interior
light/window effects) and scripted quest weathers keep their vanilla records
untouched. City worldspaces are a later pass.
"""

from __future__ import annotations

import struct

from ..model.archetypes import split_family_chance
from .reader import PluginReader, Record
from .weather import ColorType, TimeOfDay, WeatherView

TAMRIEL_WORLDSPACE = 0x0000003C

# Regions never overridden even inside Tamriel: scripted or quest-bound.
EXCLUDED_EDIDS = frozenset({
    "WeatherDA02",          # Daedric quest ambiance
})


def classify_weather(record: Record) -> str:
    """Classify a vanilla WTHR into an EW archetype name.

    Thresholds come from the vanilla data itself:
      storm rain  : rainy flag + thunder byte 255      (SkyrimStormRain)
      plain rain  : rainy flag + thunder byte 0        (SkyrimOvercastRain)
      fog         : day fog far plane pulled in to <= 30k, no precipitation
      overcast    : day-sky channel spread < 40        (gray sky)
      cloudy      : spread < 90                        (SkyrimCloudy: 76)
      clear       : spectral sky                       (SkyrimClear: 98)
    """
    view = WeatherView.from_record(record)
    if view.is_snow:
        return "snow"
    if view.is_rainy:
        return "storm" if view.data[9] > 0 else "rain"
    if view.fog.day_far <= 30000.0:
        return "fog"
    sky = view.color(ColorType.SKY_UPPER, TimeOfDay.DAY)
    spread = max(sky.r, sky.g, sky.b) - min(sky.r, sky.g, sky.b)
    if spread < 40:
        return "overcast"
    if spread < 90:
        return "cloudy"
    return "clear"


def _target_regions(vanilla: PluginReader) -> list[Record]:
    out = []
    for region in vanilla.records("REGN"):
        if region.first("RDWT") is None:
            continue
        if region.edid is None or region.edid.startswith("FX"):
            continue
        if region.edid in EXCLUDED_EDIDS:
            continue
        wnam = region.first("WNAM")
        if wnam is None:
            continue
        if struct.unpack("<I", wnam.data)[0] != TAMRIEL_WORLDSPACE:
            continue
        out.append(region)
    return out


def plan_region_overrides(vanilla: PluginReader) -> dict[str, list[tuple[str, int]]]:
    """Per targeted region: (weather name, chance) entries.

    Entries classifying to the same family merge first, so the family share
    is exact; then each family's share splits across its variants with the
    integer total preserved. Order is deterministic.
    """
    weather_by_id = {w.form_id: w for w in vanilla.records("WTHR")}
    plan: dict[str, list[tuple[str, int]]] = {}
    for region in _target_regions(vanilla):
        rdwt = region.first("RDWT").data
        shares: dict[str, int] = {}
        for offset in range(0, len(rdwt), 12):
            fid, chance, _global = struct.unpack_from("<IiI", rdwt, offset)
            family = classify_weather(weather_by_id[fid])
            shares[family] = shares.get(family, 0) + chance
        entries: list[tuple[str, int]] = []
        for family, total in sorted(shares.items()):
            entries.extend(split_family_chance(family, total))
        plan[region.edid] = entries
    return plan


def build_region_overrides(vanilla: PluginReader,
                           weather_ids: dict[str, int],
                           pack_record) -> bytes:
    """Serialized override records for every targeted region."""
    plan = plan_region_overrides(vanilla)
    records = b""
    for region in _target_regions(vanilla):
        entries = b""
        for archetype, chance in plan[region.edid]:
            entries += struct.pack("<IiI", weather_ids[archetype], chance, 0)
        subs = []
        for sub in region.subrecords:
            subs.append((sub.type, entries if sub.type == "RDWT" else sub.data))
        records += pack_record("REGN", 0, region.form_id, region.version, subs)
    return records
