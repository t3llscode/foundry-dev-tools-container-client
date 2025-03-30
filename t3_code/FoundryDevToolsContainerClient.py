from fastapi import WebSocket
from datetime import datetime
import websockets
import json

from .Schedule import Schedule

# Module by https://t3l.ls
# Universal Excel Formatter

class FoundryDevToolsContainerClient:

    def __init__(self, host: str ="project-fdt-container", port: int = 8000, log: bool = False, log_func: callable = ...):
        # TODO: in the future might also support http/s protocol
        # TODO: implement log_func

        self.url_base = f"ws://{host}:{port}/dataset"

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

            async with websockets.connect(f"{self.url_base}/get") as inner_ws: 
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
                
        except Exception as e:
            self.log_func(self, f"Error: {e}")


    async def get_single(
        self,
        outer_ws: WebSocket,
        name: str,
        from_dt: datetime,
        to_dt: datetime,
        response_func: callable = ...
    ) -> tuple[dict[str, str], bool]:
        try:
            print(response_func is ..., flush=True)
            response_func = FoundryDevToolsContainerClient.default_send_message if response_func is ... else response_func
            print(response_func, flush=True)

            async with websockets.connect(f"{self.url_base}/get") as inner_ws: 
                await self.log_func(self, "Connected to WebSocket")

                # Send initial request with DATASET_NAMES
                initial_request = {"names": [name], "from_dt": from_dt.isoformat(), "to_dt": to_dt.isoformat()}
                await inner_ws.send(json.dumps(initial_request))
                await self.log_func(self, f"Sent initial request: {initial_request}")

                # Listen for responses
                async for message in inner_ws:
                    response = json.loads(message)
                    await self.log_func(self, f"Received: {response}")

                    # proxy the reponse to the outer_ws
                    if response_func:
                        await response_func(self, outer_ws, response)

                    # type final marks the last message in the stream
                    if response.get("type") == "final":
                        return response, True
                
        except Exception as e:
            await self.log_func(self, f"Error: {e}")
            return {}, False


    # - - - Default Functions - - -

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
            print(f"Log: {message}")
