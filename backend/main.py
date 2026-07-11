from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .data_service import (
    detect_himawari_cells,
    get_frame,
    get_point_series,
    get_sources,
    get_timestamps,
    get_variable_info,
)
from .sites import get_alerts, get_site_conditions, get_sites

app = FastAPI(title="CUACADX API — Mining Weather Intelligence", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/sources")
def list_sources():
    return {"sources": get_sources()}


@app.get("/api/sources/{source}/variables")
def list_variables(source: str):
    srcs = get_sources()
    for s in srcs:
        if s["id"] == source:
            return {"variables": [get_variable_info(v) for v in s["variables"]]}
    return {"variables": []}


@app.get("/api/sources/{source}/{var}/timestamps")
def timestamps(source: str, var: str):
    return {"timestamps": get_timestamps(source, var)}


@app.get("/api/sources/{source}/{var}/frame")
def frame(
    source: str,
    var: str,
    ts: str = Query(..., description="Timestamp string"),
):
    return {"points": get_frame(source, var, ts)}


@app.get("/api/sources/himawari9/bt/cells")
def storm_cells(ts: str = Query(..., description="Timestamp string")):
    return {"cells": detect_himawari_cells(ts)}


@app.get("/api/sources/{source}/{var}/point")
def point_series(
    source: str,
    var: str,
    lat: float = Query(...),
    lon: float = Query(...),
):
    return {"series": get_point_series(source, var, lat, lon)}


# ── Mining Dashboard Endpoints ─────────────────────────────────────


@app.get("/api/sites")
def list_sites():
    return {"sites": get_sites()}


@app.get("/api/sites/conditions")
def site_conditions(site_id: str | None = None):
    return {"conditions": get_site_conditions(site_id)}


@app.get("/api/alerts")
def alerts(site_id: str | None = None):
    return {"alerts": get_alerts(site_id)}
