import asyncio
import json
import websockets
import time
import logging
import tracemalloc
import numpy as np
import argparse
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
from modelscope.utils.logger import get_logger

tracemalloc.start()
logger = get_logger(log_level=logging.CRITICAL)
logger.setLevel(logging.CRITICAL)

parser = argparse.ArgumentParser()
parser.add_argument("--host",
                    type=str,
                    default="127.0.0.1",
                    required=False,
                    help="host ip, localhost, 0.0.0.0")
parser.add_argument("--port",
                    type=int,
                    default=10095,
                    required=False,
                    help="grpc server port")
parser.add_argument("--asr_model",
                    type=str,
                    default="./FunASR/model/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                    help="model from modelscope")
parser.add_argument("--vad_model",
                    type=str,
                    default="./FunASR/model/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                    help="model from modelscope")
parser.add_argument("--punc_model",
                    type=str,
                    default="./FunASR/model/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727",
                    help="model from modelscope")
parser.add_argument("--ngpu",
                    type=int,
                    default=1,
                    help="0 for cpu, 1 for gpu")
parser.add_argument("--ncpu",
                    type=int,
                    default=4,
                    help="cpu cores")

args, _ = parser.parse_known_args()


websocket_users = set()

print("model loading")
# asr
inference_pipeline_asr = pipeline(
    task=Tasks.auto_speech_recognition,
    model=args.asr_model,
    ngpu=args.ngpu,
    ncpu=args.ncpu,
    model_revision=None)


# vad
inference_pipeline_vad = pipeline(
    task=Tasks.voice_activity_detection,
    model=args.vad_model,
    model_revision=None,
    mode='online',
    ngpu=args.ngpu,
    ncpu=args.ncpu,
)

if args.punc_model != "":
    inference_pipeline_punc = pipeline(
        task=Tasks.punctuation,
        model=args.punc_model,
        model_revision="v1.0.2",
        ngpu=args.ngpu,
        ncpu=args.ncpu,
    )
else:
    inference_pipeline_punc = None


print("model loaded! only support one client at the same time now!!!!")

async def ws_reset(websocket):
    print("ws reset now, total num is ",len(websocket_users))
    websocket.param_dict_vad = {'in_cache': dict(), "is_final": True}
    await websocket.close()
    
async def clear_websocket():
   for websocket in websocket_users:
       await ws_reset(websocket)
   websocket_users.clear()
 
async def ws_serve(websocket):
    frames = []
    frames_asr = []
    global websocket_users
    await clear_websocket()
    websocket_users.add(websocket)
    websocket.param_dict_asr = {}
    websocket.param_dict_vad = {'in_cache': dict(), "is_final": False}
    websocket.param_dict_punc = {'cache': list()}
    websocket.vad_pre_idx = 0
    speech_start = False
    speech_end_i = -1
    websocket.mode = "2pass"
    print("new user connected", flush=True)

    try:
        async for message in websocket:
            if isinstance(message, str):
                messagejson = json.loads(message)
                if "is_speaking" in messagejson:
                    websocket.is_speaking = messagejson["is_speaking"]
                if "mode" in messagejson:
                    websocket.mode = messagejson["mode"]

            if not isinstance(message, str) and websocket.is_speaking:
                frames.append(message)
                duration_ms = len(message)//32
                websocket.vad_pre_idx += duration_ms
    
                if speech_start:
                    frames_asr.append(message)

                speech_start_i, speech_end_i = await async_vad(websocket, message)
                if speech_start_i != -1:
                    await websocket.send(json.dumps({"state": "start"}))
                    speech_start = True
                    beg_bias = (websocket.vad_pre_idx-speech_start_i)//duration_ms
                    frames_pre = frames[-beg_bias:]
                    frames_asr = []
                    frames_asr.extend(frames_pre)

                if speech_end_i != -1:
                    audio_in = b"".join(frames_asr)
                    await async_asr(websocket, audio_in)
                    frames_asr = []
                    speech_start = False
                if len(frames)>=50:
                    frames = frames[-50:]
            elif not websocket.is_speaking:
                websocket.vad_pre_idx = 0
                frames = []
                websocket.param_dict_vad = {'in_cache': dict()}

    except websockets.ConnectionClosed:
        print("ConnectionClosed...", websocket_users,flush=True)
        await ws_reset(websocket)
        websocket_users.remove(websocket)
    except websockets.InvalidState:
        print("InvalidState...")
    except Exception as e:
        print("Exception:", e)

async def async_vad(websocket, audio_in):
    segments_result = inference_pipeline_vad(audio_in=audio_in, param_dict=websocket.param_dict_vad)
    speech_start = -1
    speech_end = -1
    if len(segments_result) == 0 or len(segments_result["text"]) > 1:
        return speech_start, speech_end
    if segments_result["text"][0][0] != -1:
        speech_start = segments_result["text"][0][0]
    if segments_result["text"][0][1] != -1:
        speech_end = segments_result["text"][0][1]
    return speech_start, speech_end

async def async_asr(websocket, audio_in):
            if len(audio_in) > 0:
                rec_result = inference_pipeline_asr(audio_in=audio_in,
                                                    param_dict=websocket.param_dict_asr)
                if inference_pipeline_punc is not None and 'text' in rec_result and len(rec_result["text"])>0:
                    rec_result = inference_pipeline_punc(text_in=rec_result['text'],
                                                         param_dict=websocket.param_dict_punc)
                if 'text' in rec_result:
                    message = json.dumps({"state": "complete", "text": rec_result["text"]})
                    await websocket.send(message)

start_server = websockets.serve(ws_serve, args.host, args.port, subprotocols=["binary"], ping_interval=None)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
