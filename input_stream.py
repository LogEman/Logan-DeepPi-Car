#!/usr/bin/python3
import os
import time
import atexit
import termios, fcntl, sys, os
import select
import pygame
import websockets

import asyncio
import json
from websockets.asyncio.server import serve
from datetime import datetime

from multiprocessing import Process, Lock, Array, Value

# WEB INPUT
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from functools import partial
import json

#import cv2
#import logging
#import params
#camera   = __import__(params.camera)

class input_stream:
    def __init__(self, speed=50):
        self.buffer = ' '
        self.direction = 0.
        self.speed = speed

    def read_inp():
        return self.buffer, self.direction

    def stop(self):
        return

    def __del__(self):
        self.stop()

class input_kbd(input_stream):
    def __init__(self, speed=50):
        super().__init__(speed)

    def init(self):
        fd = sys.stdin.fileno()
        # save old state
        flags_save = fcntl.fcntl(fd, fcntl.F_GETFL)
        attrs_save = termios.tcgetattr(fd)
        # make raw - the way to do this comes from the termios(3) man page.
        attrs = list(attrs_save) # copy the stored version to update
        # iflag
        attrs[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK 
                      | termios.ISTRIP | termios.INLCR | termios. IGNCR 
                      | termios.ICRNL | termios.IXON )
        # oflag
        attrs[1] &= ~termios.OPOST
        # cflag
        attrs[2] &= ~(termios.CSIZE | termios. PARENB)
        attrs[2] |= termios.CS8
        # lflag
        attrs[3] &= ~(termios.ECHONL | termios.ECHO | termios.ICANON
                      | termios.ISIG | termios.IEXTEN)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        # turn off non-blocking
        fcntl.fcntl(fd, fcntl.F_SETFL, flags_save & ~os.O_NONBLOCK)
        # read a single keystroke
        return (flags_save, attrs_save)
    
    def deinit(self,state):
        fd = sys.stdin.fileno()
        # restore old state
        termios.tcsetattr(fd, termios.TCSAFLUSH, state[1])
        fcntl.fcntl(fd, fcntl.F_SETFL, state[0])
     
    def read_inp(self):
        state = self.init()    
        r, w, e = select.select([sys.stdin], [], [], 0.000)
        self.buffer = ' '
        for s in r:
            if s == sys.stdin:
                self.buffer = sys.stdin.read(1)
                break
        self.deinit(state)

        if self.buffer == 'j': # left
            self.direction = -1.0
        elif self.buffer == 'l': # right
            self.direction = 1.0
        elif self.buffer == 'k': # center
            self.direction = .0

        return self.buffer, self.direction, self.speed
    
class input_gamepad:
    def __init__(self, speed=50, port=8080):
        self.speed = speed
        self.lock = Lock()
        self.shared_arr = Array('d', [0.0] * 8)  # [direction, speed, buttons...]
        self.port = port
        self.server_process = Process(target=self._start_server, daemon=True)
        self.server_process.start()
        print(f"WebSocket gamepad server started on port {port}")

    # ────────────────────────────────────────────────
    # Async WebSocket handler
    async def _websocket_handler(self, websocket):
        print("Browser client connected.")
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except Exception as e:
                    print("Bad JSON:", e)
                    continue

                lx = float(data.get("lx", 0.0))
                ly = float(data.get("ly", 0.0))
                r2 = float(data.get("r2", 0.0))
                l2 = float(data.get("l2", 0.0))
                buttons = data.get("buttons", {})

                # Convert triggers to speed control (-1 to 1)
                speed_val = r2 - l2
                direction_val = lx

                # Map buttons into indices [2..7]
                with self.lock:
                    self.shared_arr[0] = direction_val
                    self.shared_arr[1] = speed_val

                    # Reset and reassign button states
                    for i in range(2, 8):
                        self.shared_arr[i] = 0.0

                    if buttons.get("triangle"): self.shared_arr[2] = 1.0  # stop
                    if buttons.get("circle"):   self.shared_arr[3] = 1.0  # record
                    if buttons.get("start"):    self.shared_arr[4] = 1.0  # toggle DNN
                    if buttons.get("select"):   self.shared_arr[5] = 1.0  # quit
                    if buttons.get("square"):   self.shared_arr[6] = 1.0  # toggle video

        except Exception as e:
            print("Connection error:", e)
        finally:
            print("Browser client disconnected.")

    # ────────────────────────────────────────────────
    # Start WebSocket server
    async def _run_server(self):
        async with websockets.serve(self._websocket_handler, "0.0.0.0", self.port):
            print("WebSocket server running.")
            await asyncio.Future()  # keep alive

    def _start_server(self):
        asyncio.run(self._run_server())

    # ────────────────────────────────────────────────
    # Input reading interface
    def read_inp(self):
        self.lock.acquire()
        direction = self.shared_arr[0]
        speed_val = self.shared_arr[1]
        buffer = ' '

        # Match original keymap output logic
        if self.shared_arr[2] == 1.0:
            self.shared_arr[2] = 0.0
            buffer = 's'  # stop
        elif self.shared_arr[3] == 1.0:
            self.shared_arr[3] = 0.0
            buffer = 'r'  # record
        elif self.shared_arr[4] == 1.0:
            self.shared_arr[4] = 0.0
            buffer = 'd'  # toggle DNN
        elif self.shared_arr[5] == 1.0:
            self.shared_arr[5] = 0.0
            buffer = 'q'  # quit
        elif self.shared_arr[6] == 1.0:
            self.shared_arr[6] = 0.0
            buffer = 't'  # toggle video

        self.lock.release()

        # Convert normalized speed to actual scale
        return buffer, direction, speed_val * self.speed

    def stop(self):
        print("Stopping WebSocket server process.")
        self.server_process.terminate()

    
    

class input_gamepad(input_stream):
    def __init__(self, speed=50):
        self.shared_arr = Array('d', [0.]*8) # joystick pos and other buttons and finish state
        #self.finish = Value('i', 1)
        self.lock=Lock()
        self.gamepad_process = Process(target=self.inputs_process, \
                args=(), daemon=True )#args=(self.shared_arr, self.finish, lock,))
        self.gamepad_process.start()
        super().__init__(speed)

    def inputs_process(self): #shr_gamepad_state, finish, lock):
        import inputs
        pads = inputs.devices.gamepads
        if len(pads) == 0:
            raise Exception("Couldn't find any Gamepads!")

        #shr_gamepad_state, finish, lock = self.shared_arr, self.finish, self.lock
        shr_gamepad_state, lock = self.shared_arr, self.lock
        # Empty buffer
        gamepad_events = inputs.get_gamepad()
        print('Joystick is ready')

        disable_joystick=False
        while True: #finish.value != 0:
            gamepad_events = inputs.get_gamepad()
            if disable_joystick and time.time() - gamepad_disable_time > 0.3: # 300 ms
                disable_joystick = False
            lock.acquire()
            for event in gamepad_events:
                if not disable_joystick and event.ev_type == 'Absolute' and event.code == 'ABS_X':
                    val = int(event.state)
                    if val <= -256 or val >= 256: # calib, dead area
                        shr_gamepad_state[0] = val / 32768 #/ -32768 to 32767
                elif event.ev_type == 'Absolute' and event.code == 'ABS_HAT0Y':
                    if int(event.state) == -1:
                        shr_gamepad_state[1]=1.
                    elif int(event.state) == 1:
                        shr_gamepad_state[2]=1.
                elif event.ev_type == 'Absolute' and event.code == 'ABS_HAT0X':
                    if int(event.state) == -1:
                        shr_gamepad_state[0]= -1.
                    elif int(event.state) == 1:
                        shr_gamepad_state[0]= 1.
                    elif int(event.state) == 0:
                        shr_gamepad_state[0]= 0.
                elif event.ev_type == 'Key' and event.code == 'BTN_NORTH' and int(event.state) == 1:
                    shr_gamepad_state[3]=1. # stop
                elif event.ev_type == 'Key' and event.code == 'BTN_EAST' and int(event.state) == 1:
                    shr_gamepad_state[4]=1. # record
                elif event.ev_type == 'Key' and event.code == 'BTN_START' and int(event.state) == 1:
                    shr_gamepad_state[5]=1.
                elif event.ev_type == 'Key' and event.code == 'BTN_SELECT':
                    shr_gamepad_state[6]=1.
                    #finish.value=1
                elif event.ev_type == 'Key' and event.code == 'BTN_WEST' and int(event.state) == 1:
                    shr_gamepad_state[7]=1.
                elif event.ev_type == 'Key' and event.code == 'BTN_SOUTH' and int(event.state) == 1:
                    shr_gamepad_state[0]=0.
                    disable_joystick=True
                    gamepad_disable_time = time.time()
            #if shr_gamepad_state[0] < 32768//2 and shr_gamepad_state[0] > -32768//2:
            #    shr_gamepad_state[0] = 0. # dead area
            lock.release()

    def read_inp(self):
        self.buffer = ' '
        self.lock.acquire()
        if self.shared_arr[1] == 1.:
            self.shared_arr[1] = 0.
            self.buffer='a'
            #print ("accel")
        elif self.shared_arr[2] == 1.:
            self.shared_arr[2] = 0.
            self.buffer='z'
            #print ("reverse")
        elif self.shared_arr[3] == 1.:
            self.shared_arr[3] = 0.
            self.buffer='s'
            #print ("stop")
        elif self.shared_arr[4] == 1.:
            self.shared_arr[4] = 0.
            self.buffer='r'
            #print ("toggle record mode")
        elif self.shared_arr[5] == 1.:
            self.shared_arr[5] = 0.
            self.buffer='d'
            #print ("toggle DNN mode")
        elif self.shared_arr[6] == 1.:
            self.shared_arr[6] = 0.
            self.buffer='q'
            #self.finish.value = 0
        elif self.shared_arr[7] == 1.:
            self.shared_arr[7] = 0.
            self.buffer='t'
            #print ("toggle video mode")

        self.direction = self.shared_arr[0] 
        self.lock.release()

        return self.buffer, self.direction, self.speed

    def stop(self):
        #self.finish.value = 0
        self.gamepad_process.terminate()


class input_web_handler(BaseHTTPRequestHandler):
    def __init__(self, shared_arr, lock, *args, **kwargs):
        self.shared_arr = shared_arr
        self.lock = lock
        #cfg_cam_res = (320, 240)
        #self.cfg_cam_fps = 20
        #camera.init(res=cfg_cam_res, fps=self.cfg_cam_fps, threading=True)
        super().__init__(*args, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS, POST')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        else:
            self.send_error(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/actuate':
            self.send_response(301)
            self.end_headers()
            self.data_string = self.rfile.read(int(self.headers['Content-Length']))

            data = json.loads(self.data_string)
            self.lock.acquire()
            if data['params']['direction'] == 'left':
                self.shared_arr[0] = -1.
            elif data['params']['direction'] == 'center':
                self.shared_arr[0] = 0.
            elif data['params']['direction'] == 'right':
                self.shared_arr[0] = 1.
            elif data['params']['direction'] == 'forward':
                self.shared_arr[1] = 1.
            elif data['params']['direction'] == 'stop':
                self.shared_arr[3] = 1. 
            elif data['params']['direction'] == 'reverse':
                self.shared_arr[2] = 1.

            self.shared_arr[8] = float(data['params']['speed'])
            self.lock.release()
            #actuator.set_speed(data['params']['speed'])
        elif self.path == '/record':
            self.send_response(301)
            self.end_headers()
            self.data_string = self.rfile.read(int(self.headers['Content-Length']))

            data = json.loads(self.data_string)

            self.lock.acquire()
            self.shared_arr[4] = 1. 
            self.lock.release()


        elif self.path == '/dnn':
            self.send_response(301)
            self.end_headers()
            self.data_string = self.rfile.read(int(self.headers['Content-Length']))

            data = json.loads(self.data_string)

            self.lock.acquire()
            self.shared_arr[5] = 1. 
            self.lock.release()
            #if data['params']['action'] == 'start':
            #    use_dnn = True
            #if data['params']['action'] == 'stop':
            #    use_dnn = False


# this takes the p
class input_web(input_stream):
    def __init__(self, speed=50):
        self.shared_arr = Array('d', [0.]*9) # joystick pos and other buttons and finish state
        self.lock = Lock()

        self.ws_process = Process(target=self.web_server_process, \
                args=(), daemon=True )
        self.ws_process.start()
        super().__init__(speed)

    def web_server_process(self):
        address = ('', 8000) # backend - frontend connection
        handler = partial(input_web_handler, self.shared_arr, self.lock)
        #server = HTTPServer(address, handler)
        server = ThreadingHTTPServer(address, handler)
        try:
            server.serve_forever(poll_interval=0.05) # until terminated
        except KeyboardInterrupt:
            pass
        server.server_close()

    def read_inp(self):
        self.buffer = ' '
        self.lock.acquire()
        if self.shared_arr[1] == 1.:
            self.shared_arr[1] = 0.
            self.buffer='a'
            #print ("accel")
        elif self.shared_arr[2] == 1.:
            self.shared_arr[2] = 0.
            self.buffer='z'
            #print ("reverse")
        elif self.shared_arr[3] == 1.:
            self.shared_arr[3] = 0.
            self.buffer='s'
            #print ("stop")
        elif self.shared_arr[4] == 1.:
            self.shared_arr[4] = 0.
            self.buffer='r'
            #print ("toggle record mode")
        elif self.shared_arr[5] == 1.:
            self.shared_arr[5] = 0.
            self.buffer='d'
            #print ("toggle DNN mode")
        elif self.shared_arr[6] == 1.:
            self.shared_arr[6] = 0.
            self.buffer='q'
            #self.finish.value = 0
        elif self.shared_arr[7] == 1.:
            self.shared_arr[7] = 0.
            self.buffer='t'
            #print ("toggle video mode")

        self.direction = self.shared_arr[0] 
        self.speed = self.shared_arr[8]
        self.lock.release()

        return self.buffer, self.direction, self.speed

    def stop(self):
        self.ws_process.terminate()

class input_type:
    KEYBOARD=0
    GAMEPAD=1
    WEB=2

def instantiate_inp_stream(inp_type, def_throttle):
    inp_stream = None
    if inp_type == input_type.KEYBOARD:
        inp_stream= input_kbd(def_throttle)
    elif inp_type == input_type.GAMEPAD:
        inp_stream= input_gamepad(def_throttle)
    elif inp_type == input_type.WEB:
        inp_stream= input_web(def_throttle)

    return inp_stream
