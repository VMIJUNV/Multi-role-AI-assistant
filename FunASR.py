import websockets
import asyncio
import json
import pyaudio
import threading

class ASR():
    def __init__(self):
        self.host="127.0.0.1"
        self.port=10095

        self.ASRState=False
        self.StopSign=False

        self.ASRText=""

        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.CHUNK = 768
        self.pyaudio = pyaudio.PyAudio()
        self.stream=self.pyaudio.open(format=self.FORMAT,channels=self.CHANNELS,rate=self.RATE,input=True,frames_per_buffer=self.CHUNK)
        
        
    def run_main(self):
        asyncio.run(self.ws_client())
    def enable(self):
        threading.Thread(target=self.run_main).start()

    async def run_state(self,state):
        await self.websocket.send(json.dumps({"is_speaking": state}))
    def start(self):
        self.ASRText=""
        self.StopSign=False
        asyncio.run(self.run_state(True))
    def stop(self):
        self.StopSign=True
        asyncio.run(self.run_state(False))

    def GetState(self):
        return self.ASRState
    def GetText(self):
        return self.ASRText

    async def record_microphone(self):
        await self.websocket.send(json.dumps({"is_speaking": True}))
        while True:
            data = self.stream.read(self.CHUNK)
            await self.websocket.send(data)
            await asyncio.sleep(0.005)

    async def message(self):
        while True:
            meg = await self.websocket.recv()
            meg = json.loads(meg)
            if __name__ == '__main__':
                print(meg)
            if not self.StopSign:
                if meg["state"] == "complete":
                    self.ASRText +=meg["text"]
                    self.ASRState=False
                elif meg["state"] == "start":
                    self.ASRState=True
            await asyncio.sleep(0.05)

    async def ws_client(self):
        uri = "wss://{}:{}".format(self.host, self.port)
        print("ASR connect to", uri)
        async with websockets.connect(uri, subprotocols=["binary"], ping_interval=None, ssl=False) as websocket:
            self.websocket=websocket
            task1 = asyncio.create_task(self.record_microphone())
            task2 = asyncio.create_task(self.message())
            await asyncio.gather(task1, task2)
            
if __name__ == '__main__':
    A=ASR()
    A.enable()
