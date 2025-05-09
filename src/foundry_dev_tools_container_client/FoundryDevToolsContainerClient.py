from fastapi import WebSocket
from datetime import datetime
import polars as pl
import websockets
import traceback
import json
import io

from .Schedule import Schedule
import aiohttp

# Module by https://t3l.ls
# Universal Excel Formatter

class FoundryDevToolsContainerClient:

    def __init__(self, host: str ="project-fdt-container", port: int = 8000, log: bool = False, log_func: callable = ...):
        # TODO: in the future might also support http/s protocol
        # TODO: implement log_func

        self.url_base = f"ws://{host}:{port}/fdtc-api/dataset"
        self.download_url = f"http://{host}:{port}/fdtc-api/dataset/download"

        self.log = log
        self.log_func = FoundryDevToolsContainerClient.default_logger if log_func is ... else log_func


    async def get(self, outer_ws: WebSocket, names: str | list[str], response_func: callable = ...) -> dict[str, str]:
        """
        Connects to the Foundry Dev Tools WebSocket server and sends a request for dataset names.
        
        #### Args:
        names (str | list[str]): The dataset names to request.
        response_func (callable): A function to handle the response, takes three arguments: self, outer_ws and response (dict of the response of the inner_ws).

        #### Returns:
        (in progress) messages handled by the response_func
        (final) dict[str, str]: A dictionary containing the dataset names and their corresponding data as csv strings.
        """
        try:
            response_func = FoundryDevToolsContainerClient.default_send_message if response_func is ... else response_func

            async with websockets.connect(
                f"{self.url_base}/get",
                ping_interval=None,  # Disable automatic pings
                ping_timeout=None,   # Disable ping timeout
                close_timeout=None,  # No timeout for closing connection
                max_size=None,       # No limit on message size
                open_timeout=None    # No timeout for opening connection
            ) as inner_ws: 
                self.log_func(self, "Connected to WebSocket")

                # Send initial request with DATASET_NAMES
                initial_request = {"names": names}
                await inner_ws.send(json.dumps(initial_request))
                self.log_func(self, f"Sent initial request: {initial_request}")

                # Listen for responses
                async for message in inner_ws:
                    response = json.loads(message)
                    self.log_func(self, f"Received: {response}")

                    # proxy the reponse to the outer_ws
                    if response_func:
                        await response_func(self, outer_ws, response)

                    # type final marks the last message in the stream
                    if response.get("type") == "final":
                        break
                
        except websockets.exceptions.ConnectionClosedError as e:
            self.log_func(self, f"WebSocket connection closed unexpectedly: {e}")
        except Exception as e:
            self.log_func(self, f"Error: {e}")


    async def get_single(
        self,
        outer_ws: WebSocket,
        name: str,
        from_dt: datetime,
        to_dt: datetime,
        response_func: callable = ...,
        schema_overwrite: dict = ...,
        use_zip: bool = False
    ) -> tuple[str, bool]:
        try:
            response_func = FoundryDevToolsContainerClient.default_send_message if response_func is ... else response_func

            async with websockets.connect(
                f"{self.url_base}/get",
                ping_interval=None,  # Disable automatic pings
                ping_timeout=None,   # Disable ping timeout
                close_timeout=None,  # No timeout for closing connection
                max_size=None,       # No limit on message size
                open_timeout=None    # No timeout for opening connection
            ) as inner_ws: 
                await self.log_func(self, "Connected to WebSocket")

                # Send initial request with DATASET_NAMES
                initial_request = {"names": [name], "from_dt": from_dt.isoformat(), "to_dt": to_dt.isoformat()}
                await inner_ws.send(json.dumps(initial_request))
                await self.log_func(self, f"Sent initial request: {initial_request}")

                # Listen for responses
                async for message in inner_ws:
                    response = json.loads(message)
                    await self.log_func(self, f"Received: {response}")

                    print("RESPONSE", response, flush=True)

                    # type final marks the last message in the stream
                    if response.get("type") == "final":
                        sha256 = response["datasets"]
                        await inner_ws.close()
                        print("CLOSED CONNECTION AS FINAL IS RECEIVED", flush=True)
                        return await self.download(sha256, schema_overwrite, use_zip)
                    
                    # proxy the reponse to the outer_ws
                    if response_func:
                        await response_func(self, outer_ws, response)
                
        except websockets.exceptions.ConnectionClosedError:
            traceback.print_exc()
            await self.log_func(self, "Server closed connection unexpectedly")
            return {}, False

        except Exception as e:
            traceback.print_exc()
            await self.log_func(self, f"get_single() Error: {e}")
            return {}, False
    

    # - - - Default Functions - - -

    async def download(self, sha256: str, schema_overwrite: dict, use_zip: bool = False):

        if use_zip:
            pass  # TODO: Implement use_zip
        else:
            url = f"{self.download_url}/csv/{sha256}"
            # Create timeout settings with no limits
            timeout = aiohttp.ClientTimeout(
                total=None,      # No total timeout
                connect=None,    # No connection timeout
                sock_connect=None,  # No socket connection timeout
                sock_read=None   # No socket read timeout
            )
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        csv_data = await response.read()
                        schema_overwrite = {} if schema_overwrite == ... else schema_overwrite
                        polars_df = pl.read_csv(
                            io.BytesIO(csv_data),
                            schema_overrides=schema_overwrite
                        )
                    await self.log_func(self, f"Downloaded and parsed {url}")
                    return polars_df, True
                
                except Exception as e:
                    await self.log_func(self, f"Error downloading from {url}: {e}")
                    return "Failed", False

    # - - - Static Default Functions - - -

    @staticmethod  # never called from the object, self will always be provided as the first argument
    async def default_send_message(self, outer_ws: WebSocket, message: dict):
        """
        Sends a message to the WebSocket server.
        
        #### Args:
        ws (WebSocket): The WebSocket connection.
        message (dict): The message to send.
        """
        try:
            await outer_ws.send_json({"message": message})
            await self.log_func(self, f"Sent message: {message}")
        except Exception as e:
            await self.log_func(self, f"Error sending message: {e}")


    @staticmethod  # never called from the object, self will always be provided as the first argument
    async def default_logger(self, message: str):
        """ Default logger function that prints messages to the console if log is enabled. """
        if self.log:
            print(f"Log: {message}", flush=True)
