"""Open, process-local endpoints for the fictional last-mile demo."""
import json
from math import cos, radians
from os import environ
from pathlib import Path
from time import time
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/demo", tags=["Last-Mile Demo"])
venue_file = Path(__file__).resolve().parents[4] / "kimbeacon_app/app/src/main/assets/demo_venue.json"
IncidentId = Annotated[int, Field(ge=0, le=65535)]


class IncidentRef(BaseModel):
    incident_id: IncidentId


class Find(IncidentRef):
    mode: Literal["lan", "ble"]


class Uplink(IncidentRef):
    kind: Literal["uplink"]
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class FindRequest(IncidentRef):
    kind: Literal["find_request"]


class Ack(BaseModel):
    kind: Literal["ack"]
    command_id: str = Field(max_length=32)


class Sighting(BaseModel):
    kind: Literal["sighting"]
    rssi: int = Field(ge=-127, le=20)


AnchorEvent = Annotated[Uplink | FindRequest | Ack | Sighting, Field(discriminator="kind")]


class Demo:
    def __init__(self):
        self.incidents = {}
        self.current = None
        self.commands = {}
        self.sighting = None

    def refresh(self):
        now = time()
        self.incidents = {
            key: value for key, value in self.incidents.items()
            if value["created_at"] + 600 > now
        }
        if self.current not in self.incidents:
            self.current = None
        if self.current is not None:
            incident = self.incidents[self.current]
            if incident["status"] == "searching" and incident["created_at"] + 10 <= now:
                incident["status"] = "timed_out"
        self.commands = {
            key: value for key, value in self.commands.items()
            if value["expires_at"] > now and value["incident_id"] == self.current
            and self.incidents[self.current]["status"] in ("searching", "located")
        }
        if self.sighting and self.sighting["seen_at"] + 30 <= now:
            self.sighting = None

    def queue(self, kind, incident_id, expires_at, **fields):
        command_id = uuid4().hex
        self.commands[command_id] = dict(
            command_id=command_id, kind=kind, incident_id=incident_id,
            expires_at=expires_at, **fields,
        )

    @staticmethod
    def venue():
        try:
            return json.loads(Path(environ.get("KINBEACON_DEMO_VENUE", venue_file)).read_text())
        except (OSError, ValueError) as exc:
            raise HTTPException(503, "Demo venue dataset unavailable") from exc

    def locate(self, incident, venue, lat, lon, simulated):
        def distance_squared(landmark):
            north, east = landmark["point"]
            return (north - lat) ** 2 + ((east - lon) * cos(radians(lat))) ** 2

        index, landmark = min(
            enumerate(venue["landmarks"]), key=lambda item: distance_squared(item[1])
        )
        result = dict(lat=lat, lon=lon, radius_m=10, landmark=landmark["name"],
                      landmark_index=index, source="simulated" if simulated else "ble")
        incident.update(status="located", result=result)
        self.commands.clear()
        if not simulated:
            self.queue("loc_result", incident["incident_id"], time() + 4, **result)

    def find(self, data):
        if data.incident_id in self.incidents:
            return self.incidents[data.incident_id]
        if self.current is not None and self.incidents[self.current]["status"] in ("searching", "located"):
            raise HTTPException(409, "A demo incident is already active")

        venue = self.venue()
        now = time()
        incident = dict(incident_id=data.incident_id, mode=data.mode, status="searching",
                        created_at=now, result=None, zone=venue["zone"])
        self.current = data.incident_id
        self.incidents[self.current] = incident
        if data.mode == "lan":
            self.locate(incident, venue, *venue["wearable"], simulated=True)
        else:
            self.queue("find_target", self.current, now + 10)
        return incident


def coordinator(request: Request) -> Demo:
    demo = request.app.state.demo
    demo.refresh()
    return demo


# These handlers run on the event loop without yielding while changing incident state.
@router.post("/find")
async def find(data: Find, request: Request):
    return coordinator(request).find(data)


@router.get("/state")
async def state(request: Request):
    demo = coordinator(request)
    return dict(incident=demo.incidents.get(demo.current), anchor_sighting=demo.sighting)


@router.post("/reunite")
async def reunite(data: IncidentRef, request: Request):
    demo = coordinator(request)
    incident = demo.incidents.get(data.incident_id)
    if not incident:
        raise HTTPException(404, "Unknown demo incident")
    if incident["status"] not in ("located", "reunited"):
        raise HTTPException(409, "Wait for a location result first")
    incident["status"] = "reunited"
    demo.refresh()
    return incident


@router.get("/anchor/commands")
async def commands(request: Request):
    return list(coordinator(request).commands.values())


@router.post("/anchor/events")
async def event(data: AnchorEvent, request: Request):
    demo = coordinator(request)
    if isinstance(data, Sighting):
        demo.sighting = dict(rssi=data.rssi, seen_at=time())
    elif isinstance(data, Ack):
        demo.commands.pop(data.command_id, None)
    elif isinstance(data, FindRequest):
        demo.find(Find(incident_id=data.incident_id, mode="ble"))
    elif data.incident_id == demo.current:
        incident = demo.incidents[demo.current]
        if incident["status"] == "searching":
            demo.locate(incident, demo.venue(), data.lat, data.lon, simulated=False)
    return {"ok": True}
