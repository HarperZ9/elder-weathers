"""Bethesda plugin reader: TES4 header, group walk, record and subrecord split.

Reads .esm/.esp files in the Skyrim Special Edition form of the format.
Standard library only. Compressed records (flag 0x00040000) are inflated
with zlib. The XXXX large-subrecord escape is honored.

The reader is deliberately record-agnostic: it splits structure and leaves
field interpretation to the caller, so ground-truth tests can compare raw
bytes against the game's own master files.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

_RECORD_HEADER = struct.Struct("<4sIIIHHHH")  # type, dataSize, flags, formID, ts, vcs, version, unk
_GROUP_HEADER = struct.Struct("<4sI4siHHHH")  # 'GRUP', size, label, groupType, ts, unk, version, unk
_SUBRECORD_HEADER = struct.Struct("<4sH")     # type, size

FLAG_MASTER = 0x00000001
FLAG_LIGHT = 0x00000200
FLAG_COMPRESSED = 0x00040000


@dataclass(frozen=True)
class Subrecord:
    type: str
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class Record:
    record_type: str
    flags: int
    form_id: int
    version: int
    subrecords: tuple[Subrecord, ...]

    @property
    def is_master(self) -> bool:
        return bool(self.flags & FLAG_MASTER)

    @property
    def is_compressed(self) -> bool:
        return bool(self.flags & FLAG_COMPRESSED)

    @property
    def edid(self) -> str | None:
        for sub in self.subrecords:
            if sub.type == "EDID":
                return sub.data.rstrip(b"\x00").decode("cp1252", errors="replace")
        return None

    def first(self, sub_type: str) -> Subrecord | None:
        for sub in self.subrecords:
            if sub.type == sub_type:
                return sub
        return None

    def all(self, sub_type: str) -> list[Subrecord]:
        return [s for s in self.subrecords if s.type == sub_type]


def _split_subrecords(data: bytes) -> tuple[Subrecord, ...]:
    subrecords: list[Subrecord] = []
    offset = 0
    override_size: int | None = None
    total = len(data)

    while offset + _SUBRECORD_HEADER.size <= total:
        raw_type, size = _SUBRECORD_HEADER.unpack_from(data, offset)
        offset += _SUBRECORD_HEADER.size
        sub_type = raw_type.decode("ascii", errors="replace")

        if sub_type == "XXXX":
            if size != 4:
                raise ValueError(f"XXXX subrecord with size {size}")
            override_size = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            continue

        if override_size is not None:
            size = override_size
            override_size = None

        payload = data[offset:offset + size]
        if len(payload) != size:
            raise ValueError(
                f"truncated subrecord {sub_type}: wanted {size}, got {len(payload)}")
        offset += size
        subrecords.append(Subrecord(sub_type, payload))

    if offset != total:
        raise ValueError(f"trailing bytes in record data: {total - offset}")
    return tuple(subrecords)


def _parse_record(buf: bytes, offset: int) -> tuple[Record, int]:
    raw_type, data_size, flags, form_id, _ts, _vcs, version, _unk = \
        _RECORD_HEADER.unpack_from(buf, offset)
    record_type = raw_type.decode("ascii", errors="replace")
    start = offset + _RECORD_HEADER.size
    data = buf[start:start + data_size]
    if len(data) != data_size:
        raise ValueError(f"truncated record {record_type} at 0x{offset:X}")

    if flags & FLAG_COMPRESSED:
        decomp_size = struct.unpack_from("<I", data, 0)[0]
        data = zlib.decompress(data[4:])
        if len(data) != decomp_size:
            raise ValueError(
                f"decompression size mismatch in {record_type} 0x{form_id:08X}")

    record = Record(
        record_type=record_type,
        flags=flags,
        form_id=form_id,
        version=version,
        subrecords=_split_subrecords(data),
    )
    return record, start + data_size


class PluginReader:
    """Parses a plugin file into its TES4 header and per-type record lists."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        buf = self.path.read_bytes()

        self.header, offset = _parse_record(buf, 0)
        if self.header.record_type != "TES4":
            raise ValueError(f"{self.path.name}: not a plugin (no TES4 header)")

        self._by_type: dict[str, list[Record]] = {}
        total = len(buf)
        while offset < total:
            raw_type = buf[offset:offset + 4]
            if raw_type != b"GRUP":
                raise ValueError(f"expected GRUP at 0x{offset:X}, found {raw_type!r}")
            _grup, group_size, label, group_type, *_rest = \
                _GROUP_HEADER.unpack_from(buf, offset)
            end = offset + group_size
            if group_type == 0:
                type_label = label.decode("ascii", errors="replace")
                self._walk_group(buf, offset + _GROUP_HEADER.size, end, type_label)
            offset = end

    def _walk_group(self, buf: bytes, offset: int, end: int, type_label: str) -> None:
        while offset < end:
            raw_type = buf[offset:offset + 4]
            if raw_type == b"GRUP":
                group_size = struct.unpack_from("<I", buf, offset + 4)[0]
                self._walk_group(buf, offset + _GROUP_HEADER.size,
                                 offset + group_size, type_label)
                offset += group_size
            else:
                record, offset = _parse_record(buf, offset)
                self._by_type.setdefault(record.record_type, []).append(record)

    def records(self, record_type: str) -> list[Record]:
        return list(self._by_type.get(record_type, []))

    @property
    def record_types(self) -> set[str]:
        return set(self._by_type)
