import json
import os
import secrets
from datetime import datetime, timezone
from typing import Literal

import paho.mqtt.publish as publish
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URI"), tz_aware=True)
db = client["test2"]
fans = db["fans"]
readings = db["readings"]
settings = db["settings"]

fans.create_index([("mac", ASCENDING)], unique=True)
fans.create_index([("key", ASCENDING)], unique=True)

MQTT_BROKER = "135.232.203.144"
MQTT_NAME = os.getenv("MQTT_NAME", "")

app = FastAPI()


class FanIn(BaseModel):
    mac: str
    room: str


class ReadingIn(BaseModel):
    mac: str
    humidity: float = Field(ge=0, le=100)


class SettingsIn(BaseModel):
    mode: Literal["auto", "on", "off"]
    max_humidity: float = Field(ge=0, le=100)


def fan_from_key(x_api_key):
    """401 when there is no key, or the server never issued it."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key")
    fan = fans.find_one({"key": x_api_key})
    if fan is None:
        raise HTTPException(status_code=401, detail="Unknown API key")
    return fan


# A1 ------------------------------------------------------------------
@app.post("/fans", status_code=201)
def create_fan(body: FanIn):
    fan = {"mac": body.mac, "room": body.room, "key": secrets.token_urlsafe(16)}
    try:
        fans.insert_one(dict(fan))
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Fan " + body.mac + " already exists")
    return fan


@app.get("/fans")
def list_fans():
    return list(fans.find({}, {"_id": 0, "key": 0}))


@app.get("/fans/{mac}")
def get_fan(mac: str):
    fan = fans.find_one({"mac": mac}, {"_id": 0, "key": 0})
    if fan is None:
        raise HTTPException(status_code=404, detail="No fan with MAC " + mac)
    return fan


# A2 ------------------------------------------------------------------
@app.post("/readings", status_code=201)
def create_reading(body: ReadingIn, x_api_key: str | None = Header(default=None)):
    owner = fan_from_key(x_api_key)
    if owner["mac"] != body.mac:
        raise HTTPException(status_code=403, detail="That key belongs to another fan")
    reading = {
        "mac": body.mac,
        "humidity": body.humidity,
        "time": datetime.now(timezone.utc),
    }
    readings.insert_one(dict(reading))
    return reading


# A3 ------------------------------------------------------------------
@app.get("/readings")
def list_readings(mac: str | None = None, limit: int = Query(default=10, ge=1, le=100)):
    query = {}
    if mac is not None:
        query["mac"] = mac
    return list(readings.find(query, {"_id": 0}).sort("time", -1).limit(limit))


# A4 ------------------------------------------------------------------
@app.put("/fans/{mac}/settings")
def put_settings(mac: str, new: SettingsIn, response: Response):
    if fans.find_one({"mac": mac}) is None:
        raise HTTPException(status_code=404, detail="No fan with MAC " + mac)
    doc = {"mac": mac, "mode": new.mode, "max_humidity": new.max_humidity}
    result = settings.replace_one({"mac": mac}, doc, upsert=True)
    response.status_code = 201 if result.upserted_id is not None else 200
    payload = json.dumps({"mode": new.mode, "max_humidity": new.max_humidity})
    try:
        publish.single(
            "ecse3038/" + MQTT_NAME + "/fan/settings",
            payload,
            retain=True,
            hostname=MQTT_BROKER,
        )
    except Exception as error:
        print("Could not publish the settings:", error)
    return {"mode": new.mode, "max_humidity": new.max_humidity}


# A5 ------------------------------------------------------------------
@app.delete("/fans/{mac}", status_code=204)
def delete_fan(mac: str, x_api_key: str | None = Header(default=None)):
    fan = fans.find_one({"mac": mac})
    if fan is None:
        raise HTTPException(status_code=404, detail="No fan with MAC " + mac)
    owner = fan_from_key(x_api_key)
    if owner["mac"] != mac:
        raise HTTPException(status_code=403, detail="That key belongs to another fan")
    fans.delete_one({"mac": mac})
    settings.delete_one({"mac": mac})
    return Response(status_code=204)