# Foundry DevTools Container Client

This module provides a client for easy access to the [Foundry DevTools Container Service](https://github.com/t3llscode/foundry-dev-tools-container).

> **Note:** Throughout this documentation, `FDTCC` references the `FoundryDevToolsContainerClient` class for brevity.

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/t3llscode/foundry-dev-tools-container-client.git
```

Alternatively, you may clone and install the module locally (recommended if you want to inspect or modify the code, but requires an extra step to update):

```bash
git clone https://github.com/t3llscode/foundry-dev-tools-container-client.git
pip install ./foundry-dev-tools-container-client
```

After installation, you can import the client as follows:

```python
from foundry_dev_tools_container_client import FoundryDevToolsContainerClient as FDTCC
```

> 📦 In the future, a PyPI package may be provided for even easier installation.

## Overview

`FoundryDevToolsContainerClient` offers an async WebSocket bridge to the Foundry DevTools Container Service. Beyond streaming datasets, the client now includes:

- **Incremental download helpers** via `get_single()` and `download()` returning Polars DataFrames.
- **Schedule-aware pull windows** using the bundled `Schedule` and `Refresh` classes for repeatable ingestion windows.
- **Pluggable logging/response hooks** so you can proxy messages to any outer socket or monitoring backend.

## Core API

### `FDTCC(host="project-fdt-container", port=8000, log=False, log_func=...)`

| Parameter | Type | Purpose | Default |
|-----------|------|---------|---------|
| `host` | `str` | Hostname of the service | `project-fdt-container` |
| `port` | `int` | Exposed service port | `8000` |
| `log` | `bool` | Toggle default logging | `False` |
| `log_func` | `callable` | Async logger `(self, message)` | `default_logger` |

### `await FDTCC.get(outer_ws, names, response_func=...)`

Streams one or more dataset names through the container. Each inbound message is forwarded to `response_func(self, outer_ws, message)` (defaults to `default_send_message`). When the inner service emits `type="final"` the method returns.

### `await FDTCC.get_single(outer_ws, name, from_dt, to_dt, response_func=..., schema_overwrite=..., use_zip=False)`

Retrieves a single dataset slice defined by an ISO timestamp window. The method:

1. Streams job status to `response_func` just like `get()`.
2. On `type="final"`, calls `download()` with the emitted SHA256 pointer.
3. Returns `(polars.DataFrame, bool)` where the boolean indicates download success.

Use `schema_overwrite` to pass a `dict[column]=dtype` map for Polars parsing. `use_zip` is reserved for a future compressed transport.

### `await FDTCC.download(sha256, schema_overwrite=..., use_zip=False)`

Performs a blocking HTTP download of the generated CSV and parses it with Polars. Any schema overrides are forwarded to `pl.read_csv`. On failure, the tuple `("Failed", False)` is returned.

### `Schedule` and `Refresh`

The helper classes in `Schedule.py` describe when a dataset refreshes so you can build the `from_dt`/`to_dt` window automatically.

```python
from datetime import timedelta
from foundry_dev_tools_container_client import Schedule

schedule = Schedule([
    {"cycle": "monthly", "day": 1, "time": "02:00:00"},
    {"cycle": "weekly", "day": "Monday", "time": "02:00:00"}
], buffer=timedelta(minutes=60))

last_pull = schedule.get_latest_refresh()      # includes buffer
next_pull = schedule.get_next_refresh()
```

`Schedule` stores multiple `Refresh` rules, validates them, and exposes `get_latest_refresh()` / `get_next_refresh()` helpers so your ingestion only touches new rows.

#### Building schedules with every supported cycle

Currently two cycle types are supported—`"monthly"` and `"weekly"`. You can combine as many refresh rules as you want per dataset:

```python
from datetime import timedelta
from foundry_dev_tools_container_client import Schedule

dataset_schedules = {
    # Refresh on the 1st of every month at 02:00 UTC
    "foundry.financials.month_start": Schedule([
        {"cycle": "monthly", "day": 1, "time": "02:00:00"}
    ], buffer=timedelta(minutes=30)),

    # Refresh every Monday (weekly accepts weekday names, case-insensitive)
    "foundry.support.weekly_snapshot": Schedule([
        {"cycle": "weekly", "day": "Monday", "time": "04:30:00"}
    ]),

    # Multiple rules: first business day + last calendar day by using negative indices
    "foundry.hr.monthly_closings": Schedule([
        {"cycle": "monthly", "day": 1, "time": "06:00:00"},      # first day
        {"cycle": "monthly", "day": -1, "time": "22:00:00"},     # last day (use -1)
        {"cycle": "weekly", "day": "Friday", "time": "08:00:00"} # weekly QA pull
    ], buffer=timedelta(hours=2))
}

# Accessing a schedule
finance_schedule = dataset_schedules["foundry.financials.month_start"]
latest = finance_schedule.get_latest_refresh()
next_up = finance_schedule.get_next_refresh()
```

Rules recap:

- `monthly`: `day` is an integer (1–31) or a negative integer (-1 = last day, -2 = second to last, ...).
- `weekly`: `day` is a weekday string (Monday–Sunday).
- `time`: always `HH:MM:SS` in 24h UTC.
- `buffer` (optional): `timedelta` that shifts the calculated timestamps forward, handy when the source system needs extra processing time.

## Usage Examples

### Streaming multiple datasets

```python
from fastapi import WebSocket
import json

from foundry_dev_tools_container_client import FoundryDevToolsContainerClient as FDTCC

def custom_log(self: FDTCC, message: str):
    if self.log:
        print(f"Custom Log - {self.host}:{self.port} - {message}")

async def custom_response(self: FDTCC, outer_ws: WebSocket, message: str):
    await outer_ws.send_json(message)
    await self.log_func(self, f"Sent message: {message}")

fdtcc_client = FDTCC(host="project-fdt-container", port=8000, log=True, log_func=custom_log)

@router.websocket("/insert_dataset")
async def insert_dataset(outer_ws: WebSocket):
    await outer_ws.accept()
    payload = await outer_ws.receive_json()
    names = payload.get("names", [])
    await fdtcc_client.get(outer_ws, names, custom_response)
```

### Incremental download with `Schedule`

```python
from datetime import datetime
from fastapi import WebSocket
from foundry_dev_tools_container_client import FoundryDevToolsContainerClient as FDTCC, Schedule

schedule = Schedule([
    {"cycle": "weekly", "day": "Monday", "time": "02:00:00"}
])

fdtcc_client = FDTCC(log=True)

@router.websocket("/pull_dataset")
async def pull_dataset(ws: WebSocket):
    await ws.accept()

    end = schedule.get_next_refresh()
    start = schedule.get_latest_refresh()

    df, ok = await fdtcc_client.get_single(
        ws,
        name="foundry.my_dataset",
        from_dt=start,
        to_dt=end,
    )

    if ok:
        # df is a polars.DataFrame
        await ws.send_json({"message": f"Received {df.height} rows"})
    else:
        await ws.send_json({"error": "Download failed"})
```

## Requirements

- Python 3.10+
- fastapi (outer WebSocket contracts)
- websockets
- polars
- aiohttp
- pytz

---

<div align="center">

a [t3lls](https://t3l.ls) module

</div>
