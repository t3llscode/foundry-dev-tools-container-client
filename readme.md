# Foundry DevTools Container Client

This module provides a client for easy access to the [Foundry DevTools Container Service](https://github.com/t3llscode/foundry-dev-tools-container).

> **Note:** Throughout this documentation, `FDTCC` is used as a short name for `FoundryDevToolsContainerClient` for brevity.

## Installation

For proper IDE intellisense support (e.g., PyLance), you'll need to ensure the module can be imported statically without sys path manipulations. Since Python module names cannot contain dashes, use this approach:

```bash
git clone https://github.com/t3lls/foundry-dev-tools-container-client foundry_dev_tools_container_client
```

```python
from foundry_dev_tools_container_client.t3_code.FoundryDevToolsContainerClient import FoundryDevToolsContainerClient as FDTCC
```

> In the future I want to provide a package on PyPI or an own repository so you can install it without cloning the repository.

## Overview

The `FoundryDevToolsContainerClient` is a WebSocket-based client that facilitates communication with the [Foundry DevTools Container Service](https://github.com/t3llscode/foundry-dev-tools-container). It provides an asynchronous interface for retrieving datasets from Foundry and streaming the results back through WebSocket connections.

### Key Features

- **Asynchronous WebSocket Communication**: Built on top of `websockets` and `fastapi.WebSocket` for real-time data streaming
- **Flexible Response Handling**: Customizable response and logging functions to fit your application's needs
- **Proxy Pattern**: Acts as a bridge between your outer WebSocket connection and the [Foundry DevTools Container Service](https://github.com/t3llscode/foundry-dev-tools-container)
- **Error Handling**: Built-in error handling with customizable logging

## Functions and Parameters

### FDTCC()

Arguments:

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `host` | `str` | The hostname of the Foundry DevTools Container Service | `"project-fdt-container"` |
| `port` | `int` | The port number of the service | `8000` |
| `log` | `bool` | Enable/disable logging | `False` |
| `log_func` | `callable` | Custom logging function, receives `(self, message)` as arguments | `FDTCC.default_logger` |

### FDTCC.get()

Arguments:

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `outer_ws` | `WebSocket` | The outer WebSocket connection to your client | - |
| `names` | `str \| list[str]` | The dataset name(s) to request from Foundry | - |
| `response_func` | `callable` | Custom function to handle responses, receives `(self, outer_ws, message)` as arguments | `FDTCC.default_send_message` |

Returns:

| Return Type | Description |
|-------------|-------------|
| `dict[str, str]` | A dictionary mapping dataset names to their corresponding CSV data |
| During execution | Streams responses through the provided `response_func` |

## Usage Example

You can freely set functions for logging and response handling. If you dont choose any there are default functions which will be used. The client will call these functions with the following arguments:

- <b>log_func</b>: ```(self: <FoundryDevToolsContainerClient>, message: str)```
- <b>response_func</b>: ```(self: <FoundryDevToolsContainerClient>, outer_ws: <fastapi.WebSocket>, message: str)```

```python
from fastapi import WebSocket
import json

# you might need to do it like this, as there are dashs in the module name
FDTCC = __import__('modules.foundry-dev-tools-container-client.t3_code.FoundryDevToolsContainerClient', fromlist=['FoundryDevToolsContainerClient']).FoundryDevToolsContainerClient

# - - - INITIALIZE CUSTOM FUNCTIONS AND CLIENT - - -

def custom_log(self: FDTCC, message: str):
    if self.log:
        print(f"Custom Log - {self.host}:{self.port} - {message}")

async def custom_response(self: FDTCC, outer_ws: WebSocket, message: str):
    try:
        await outer_ws.send(json.dumps(message))
        self.log_func(self, f"Sent message: {message}")
    except Exception as e:
        self.log_func(self, f"Error sending message: {e}")

fdtcc_client = FDTCC(
    # protocol - may be added in the future, currently only supporting ws
    host = "project-fdt-container",
    port = 8000,
    log = True,
    log_func = custom_log,  # Custom logging function
)

# - - - OUTER WEBSOCKET CALL - - -

@router.websocket("/insert_dataset")
async def insert_dataset(outer_ws: WebSocket):
    try:
        await outer_ws.accept()

        initial_req = await outer_ws.receive_json()
        names = initial_req.get("names", [])

        # This will retrieve the dataset and forward all messages to the outer_ws
        dataset_info = fdtcc_client.get(outer_ws, names, custom_response)

        for df_name, df in dataset_info.items():
            print(f"DataFrame Name: {df_name}")
            print(f"DataFrame Content: {df}")

        # INSERT THE DATASETS HERE #

    except Exception as e:
        fdtcc_client.log_func(fdtcc_client, f"Error in WebSocket: {e}")
```

## Requirements

- Python 3.x
- fastapi
- websockets
- json

---

<div align="center">

a [t3lls](https://t3l.ls) module

</div>
