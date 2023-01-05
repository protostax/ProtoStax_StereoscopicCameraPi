# ***************************************************
#   ProtoStax Stereoscopic 3D Camera Streamer.
#   using 2x Raspberry Pi Zero W, 2x Pi Camera V2,
#   ProtoStax Enclosure for Raspberry Pi Zero
#      --> https://www.protostax.com/products/protostax-for-raspberry-pi-zero
#   and ProtoStax Stereoscopic 3D Camera Kit for Raspberry Pi Camera - 60mm Stereo Base
#      --> https://www.protostax.com/products/protostax-3d-camera-kit-for-raspberry-pi-camera
#
#   Optionally add a ProtoStax Enclosure for RPI UPSPack Standard V3
#      --> https://www.protostax.com/products/protostax-enclosure-for-rpi-upspack-standard-v3
#   and RPI UPSPack Standard V3
#   vertically stacked in the setup for a wireless and portable stereoscopic camera streamer.
#
#  This program starts streaming video over http from the left and right pi cameras
#  and places the streams side-by-side.They can be viewed with a stereoscopic
#  viewer like Google Cardboard with a mobile phone that has the page opened on a browser
#
#  With the mobile battery-based setup (using RPI UPSPack Standard V3), the camera can be
#  moved around while the viewer with the Google Cardboard can enjoy a 3D tour! 
#
#   Written by Sridhar Rajagopal for ProtoStax.
#
#
#   BSD license. All text above must be included in any redistribution

# Based on the Web Streaming Advanced Recipe from picamera
# This does not work with the latest Raspberry Pi OS Bullseye as
# picamera is incompatible with it.
# Use Raspberry Pi OS Buster instead.

import io
import picamera
import logging
import socketserver
from threading import Condition
from http import server

# This creates a web page with two video streams side-by-side that autofit the
# width of the browser.
# It assumes the two raspberry pis are named leftcam.local and rightcam.local 
# (Update the names according to your own setup)
# Open the index page on your mobile phone from either leftcam.local or rightcam.local
# to view the stereoscopic stream.
# e.g. http://leftcam.local:8000/ or http://rightcam.local:8000 
# Place the mobile phone (with the above link opened on your browser) in your 
# stereoscopic viewer (like Google Cardboard) and adust as necessary so
# that the stereoscopic 3D image appears properly
# You may want to update your mobile phone auto-lock settings so that the
# screen does not auto-lock
# E.g. on iOS:
# Settings  > Display & Brightness > Auto-Lock > Choose an appropriate length of time

PAGE="""\
<html>
  <head>
    <style>
      .viewfinder {
        display: flex;
        flex-wrap: wrap;
      }
      .viewfinder-item {
        height: 50%;
        width:  50%;
        object-fit: contain;
      }
    </style>
  </head>
  <body>
    <div class="viewfinder">
      <img class="viewfinder-item" src="http://leftcam.local:8000/stream.mjpg" />
      <img class="viewfinder-item" src="http://rightcam.local:8000/stream.mjpg" />
    </div>
  </body>
</html>
"""

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

with picamera.PiCamera(resolution='640x480', framerate=24) as camera:
    output = StreamingOutput()
    camera.start_recording(output, format='mjpeg')
    try:
        address = ('', 8000)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        camera.stop_recording()


