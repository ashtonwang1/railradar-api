import asyncio
from datetime import datetime, timezone
from typing import Annotated, Any

import requests
from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

TRAIN_NUMBER_PATTERN = r"^\d{1,5}$"
STATION_CODE_PATTERN = r"^[A-Za-z]{3}$"
PRIMARY_BASE_URL = "https://api-v3.amtraker.com"
FALLBACK_BASE_URL = "https://amtrak-api.marcmap.app"
SOURCE_BASE_URLS = [PRIMARY_BASE_URL, FALLBACK_BASE_URL]
JsonDict = dict[str, Any]


class TrainStationResponse(BaseModel):
    trainNumber: str
    origin: str
    destination: str
    currentStation: str
    queriedStation: str
    delayMinutes: int
    status: str
    asOf: str


def _to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _compute_delay_minutes(station: JsonDict) -> int:
    dep_time = _to_datetime(station.get("dep"))
    sch_dep_time = _to_datetime(station.get("schDep"))
    if dep_time and sch_dep_time:
        return int((dep_time - sch_dep_time).total_seconds() // 60)

    arr_time = _to_datetime(station.get("arr"))
    sch_arr_time = _to_datetime(station.get("schArr"))
    if arr_time and sch_arr_time:
        return int((arr_time - sch_arr_time).total_seconds() // 60)

    return 0


def _fetch_json(path: str) -> JsonDict:
    last_error: Exception | None = None
    for base_url in SOURCE_BASE_URLS:
        url = f"{base_url}{path}"
        try:
            response = requests.get(url, timeout=12)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            raise requests.RequestException("Unexpected upstream payload shape")
        except requests.RequestException as error:
            last_error = error

    raise HTTPException(
        status_code=502,
        detail="Upstream train status providers are unavailable",
    ) from last_error


def _find_train_entry(train_payload: JsonDict, train_number: str) -> JsonDict | None:
    entries = train_payload.get(train_number)
    if isinstance(entries, list) and entries:
        return entries[0]
    return None

# 核心修复：当 origins 是 ["*"] 时，allow_credentials 必须是 False
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get(
    "/api/train/{train_number}/station/{station_code}",
    response_model=TrainStationResponse,
)
async def get_train_station_info(
    train_number: Annotated[
        str,
        Path(
            pattern=TRAIN_NUMBER_PATTERN,
            description="1-5 digit train number",
        ),
    ],
    station_code: Annotated[
        str,
        Path(
            pattern=STATION_CODE_PATTERN,
            description="3-letter station code",
        ),
    ],
):
    normalized_station = station_code.upper()

    station_payload = await asyncio.to_thread(_fetch_json, f"/v3/stations/{normalized_station}")
    station_data = station_payload.get(normalized_station)
    if not isinstance(station_data, dict):
        raise HTTPException(status_code=404, detail="Station not found")

    train_ids = station_data.get("trains", [])
    if not isinstance(train_ids, list):
        raise HTTPException(status_code=404, detail="Station has no active train data")

    matched_train_id = next(
        (
            train_id
            for train_id in train_ids
            if isinstance(train_id, str) and train_id.split("-", maxsplit=1)[0] == train_number
        ),
        None,
    )
    if matched_train_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"Train {train_number} not found for station {normalized_station}",
        )

    train_payload = await asyncio.to_thread(_fetch_json, f"/v3/trains/{matched_train_id}")
    train_entry = _find_train_entry(train_payload, train_number)
    if train_entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Train {train_number} has no active detail feed",
        )

    stations = train_entry.get("stations", [])
    station_entry = next(
        (
            station
            for station in stations
            if isinstance(station, dict) and station.get("code") == normalized_station
        ),
        None,
    )
    if station_entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Station {normalized_station} is not in active itinerary for train {train_number}",
        )

    as_of = train_entry.get("updatedAt") or train_entry.get("lastValTS")
    if not isinstance(as_of, str):
        as_of = datetime.now(timezone.utc).isoformat()

    return TrainStationResponse(
        trainNumber=str(train_entry.get("trainNumRaw") or train_number),
        origin=str(train_entry.get("origCode") or ""),
        destination=str(train_entry.get("destCode") or ""),
        currentStation=normalized_station,
        queriedStation=normalized_station,
        delayMinutes=_compute_delay_minutes(station_entry),
        status=str(station_entry.get("status") or "Unknown"),
        asOf=as_of,
    )
