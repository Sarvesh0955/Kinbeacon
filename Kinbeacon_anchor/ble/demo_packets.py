"""Manufacturer data shared with the Android last-mile roles."""
import struct

CONTROL = 0xFFFE
UPLINK = 0xFFFD
HEARTBEAT = b"kb-demo-child"
FORMATS = ("B", "BB", "B", "Biib", "iiBB", "Bii")


def decode(company, payload):
    if len(payload) < 4:
        return None
    kind, incident_id, ttl = struct.unpack_from(">BHB", payload)
    if kind >= len(FORMATS) or company != (UPLINK if kind == 5 else CONTROL):
        return None
    format_string = ">" + FORMATS[kind]
    if len(payload) != 4 + struct.calcsize(format_string):
        return None
    fields = struct.unpack_from(format_string, payload, 4)
    if ttl not in (1, 2) or (kind != 4 and fields[0] != 1):
        return None
    if kind == 1 and (fields[1] not in (0, 1) or (fields[1] == 1 and ttl != 1)):
        return None
    if kind in (2, 3, 5) and ttl != 1:
        return None
    if kind in (3, 4, 5):
        offset = 0 if kind == 4 else 1
        lat, lon = fields[offset:offset + 2]
        if abs(lat) > 900_000_000 or abs(lon) > 1_800_000_000:
            return None
    if kind == 4 and (fields[2] != 10 or fields[3] > 1):
        return None
    return kind, incident_id, ttl, fields


def encode(kind, incident_id, ttl, *fields):
    return struct.pack(">BHB" + FORMATS[kind], kind, incident_id, ttl, *fields)
