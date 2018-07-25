import argparse
import asyncio
import json
import logging
import math
import os
import time


import av
from av.video.frame import VideoFrame as AVFrame

from aiohttp import web

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import (AudioFrame, AudioStreamTrack, VideoFrame,
                                 VideoStreamTrack)

ROOT = os.path.dirname(__file__)



async def consume_audio(track):
    
    while True:
        frame = await track.recv()
        print(frame)


async def consume_video(track):

    last_size = None

    output = av.open('rtmp://localhost/live/live',mode='w',format='flv')
    stream = output.add_stream('libx264', 24)
    stream.pix_fmt = 'yuv420p'

    while True:

        frame = await track.recv()

        print(frame)

        # print frame size
        frame_size = (frame.width, frame.height)
        if frame_size != last_size:
            print('Received frame size', frame_size)
            last_size = frame_size

        w, h = (frame.width, frame.height)

        y_start = 0
        u_start = w*h
        v_start = int(w*h + w*h/4)

        vframe = AVFrame(w, h, 'yuv420p')

        # y
        vframe.planes[0].update_buffer(frame.data[0:w*h])
        # # u
        vframe.planes[1].update_buffer(frame.data[u_start:v_start])
        # # v
        vframe.planes[2].update_buffer(frame.data[v_start:])

        # now we can push to rtmp server now 

        packet = stream.encode(vframe)
        if packet:
            output.mux(packet)

async def index(request):
    content = open(os.path.join(ROOT, 'index.html'), 'r').read()
    return web.Response(content_type='text/html', text=content)


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(
        sdp=params['sdp'],
        type=params['type'])

    pc = RTCPeerConnection()
    pc._consumers = []
    pcs.append(pc)

    @pc.on('track')
    def on_track(track):
        if track.kind == 'audio':
            pc._consumers.append(asyncio.ensure_future(consume_audio(track)))
        if track.kind == 'video':
            pc._consumers.append(asyncio.ensure_future(consume_video(track)))


    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type='application/json',
        text=json.dumps({
            'sdp': pc.localDescription.sdp,
            'type': pc.localDescription.type
        }))


pcs = []


async def on_shutdown(app):
  
    for pc in pcs:
        for c in pc._consumers:
            c.cancel()

    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='WebRTC audio / video / data-channels demo')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port for HTTP server (default: 8080)')
    parser.add_argument('--verbose', '-v', action='count')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get('/', index)
    app.router.add_post('/offer', offer)
    web.run_app(app, port=args.port)
