# ***************************************************
#   ProtoStax Stereoscopic 3D Camera Streamer.
#
#   This program starts streaming video over http from the left and right pi cameras
#   and places the streams side-by-side.They can be viewed with a stereoscopic
#   viewer like Google Cardboard with a mobile phone that has the page opened on a browser
#
#   If you use it with the Raspberry Pi 5, it assumes that there are two cameras connected
#   You can just open the page using http://yourpinamehere.local:8000/ or http://yourpinamehere.local:8000
#
#   If you use it with the Raspberry Pi Zero, it assumes there are two raspberry pis
#   named leftcam.local and rightcam.local 
#   (Update the pi names according to your own setup).
# 
#   This project has been updated to use PiCamera2
#   If you are using an older version of Raspberry Pi OS or are using the legacy camera stack
#   please use the previous version of this project, which used PiCamera. 
# 
#   Open the index page on your mobile phone from either leftcam.local or rightcam.local
#   to view the stereoscopic stream.
#   e.g. http://leftcam.local:8000/ or http://rightcam.local:8000
#
#   Place the mobile phone (with the above link opened on your browser) in your 
#   stereoscopic viewer (like Google Cardboard) and adust as necessary so
#   that the stereoscopic 3D image appears properly
#
#   This uses the NoSleep.js library prevent the auto-lock of the screen from kicking in - just toggle the button
#   
#   You may also want to update your mobile phone auto-lock settings so that the
#   screen does not auto-lock (in case there is an issue with the NoSleep.js not working)
#   E.g. on iOS:
#   Settings  > Display & Brightness > Auto-Lock > Choose an appropriate length of time
#
#   This project uses:
#   ---
#   2x Raspberry Pi Zero W, 2x Pi Camera V2,
#   ProtoStax Enclosure for Raspberry Pi Zero
#      --> https://www.protostax.com/products/protostax-for-raspberry-pi-zero
# 
#   OR
#   1x Raspberry Pi 5, 2x Pi Camera,
#   ProtoStax Enclosure for Raspberry Pi 3/4/5
#      --> https://www.protostax.com/products/protostax-for-raspberry-pi-b
#   ---
#   and ProtoStax Stereoscopic 3D Camera Kit for Raspberry Pi Camera - 60mm Stereo Base
#      --> https://www.protostax.com/products/protostax-3d-camera-kit-for-raspberry-pi-camera
#
#   Optionally add a ProtoStax Enclosure for RPI UPSPack Standard V3 (not for use with Raspberry Pi 5
#   which requires 5A)
#      --> https://www.protostax.com/products/protostax-enclosure-for-rpi-upspack-standard-v3
#   and RPI UPSPack Standard V3
#   vertically stacked in the setup for a wireless and portable stereoscopic camera streamer.
#
#  With the mobile battery-based setup (using RPI UPSPack Standard V3), the camera can be
#  moved around while the viewer with the Google Cardboard can enjoy a 3D tour! 
#
#   Written by Sridhar Rajagopal for ProtoStax.
#
#
#   BSD license. All text above must be included in any redistribution

# Based on the Web Streaming Advanced Recipe from picamera
#   This project has been updated to use PiCamera2
#   If you are using an older version of Raspberry Pi OS or are using the legacy camera stack
#   please use the previous version of this project, which used PiCamera.  

import io
import logging
import socketserver
from threading import Condition
from http import server
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput


RPIZERO_PAGE="""\
<html>
  <head>
    <link rel="shortcut icon" href="https://www.protostax.com/cdn/shop/files/Sridhar_rajagop.png?crop=center&height=32&v=1613523611&width=32" type="image/x-icon">
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
    <script type="text/javascript" src="https://richtr.github.io/NoSleep.js/dist/NoSleep.min.js"></script>

  </head>
  <body>
    <input type="button" id="toggle" value="Wake Lock is disabled" />

    <script>
      var noSleep = new NoSleep();

      var wakeLockEnabled = false;
      var toggleEl = document.querySelector("#toggle");
      toggleEl.addEventListener('click', function() {
        if (!wakeLockEnabled) {
          noSleep.enable(); // keep the screen on!
          wakeLockEnabled = true;
          toggleEl.value = "Wake Lock is enabled";
          document.body.style.backgroundColor = "black";
        } else {
          noSleep.disable(); // let the screen turn off.
          wakeLockEnabled = false;
          toggleEl.value = "Wake Lock is disabled";
          document.body.style.backgroundColor = "";
        }
      }, false);
    </script>
    <div class="viewfinder">
      <img class="viewfinder-item" src="http://leftcam.local:8000/stream.mjpg" />
      <img class="viewfinder-item" src="http://rightcam.local:8000/stream.mjpg" />
    </div>
  </body>
</html>
"""

RPI5_PAGE="""\
<html>
  <head>
    <link rel="shortcut icon" href="https://www.protostax.com/cdn/shop/files/Sridhar_rajagop.png?crop=center&height=32&v=1613523611&width=32" type="image/x-icon">
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
    <script type="text/javascript" src="https://richtr.github.io/NoSleep.js/dist/NoSleep.min.js"></script>

  </head>
  <body>
    <input type="button" id="toggle" value="Wake Lock is disabled" />

    <script>
      var noSleep = new NoSleep();

      var wakeLockEnabled = false;
      var toggleEl = document.querySelector("#toggle");
      toggleEl.addEventListener('click', function() {
        if (!wakeLockEnabled) {
          noSleep.enable(); // keep the screen on!
          wakeLockEnabled = true;
          toggleEl.value = "Wake Lock is enabled";
          document.body.style.backgroundColor = "black";
        } else {
          noSleep.disable(); // let the screen turn off.
          wakeLockEnabled = false;
          toggleEl.value = "Wake Lock is disabled";
          document.body.style.backgroundColor = "";
        }
      }, false);
    </script>
    <div class="viewfinder">
      <img class="viewfinder-item" src="leftstream.mjpg" />
      <img class="viewfinder-item" src="rightstream.mjpg" />
    </div>
  </body>
</html>
"""

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = RPI5_PAGE.encode('utf-8') if picam2right != None else RPIZERO_PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg' or self.path == '/leftstream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while outputleft != None:
                    with outputleft.condition:
                        outputleft.condition.wait()
                        frame = outputleft.frame
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
        elif self.path == '/rightstream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while outputright != None:
                    with outputright.condition:
                        outputright.condition.wait()
                        frame = outputright.frame
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

picam2Left = None
picam2right = None
outputleft = None
outputright = None

try:
    picam2left = Picamera2(0)
    picam2left.configure(picam2left.create_video_configuration(main={"size": (640, 480)}))
    outputleft = StreamingOutput()
    # picam2left.start_recording(JpegEncoder(), FileOutput(outputleft))
except Exception as e:
    print("Left")
    print(e)
    picam2left = None
    outputleft = None

try:
    picam2right = Picamera2(1)
    picam2right.configure(picam2right.create_video_configuration(main={"size": (640, 480)}))
    outputright = StreamingOutput()
    # picam2right.start_recording(JpegEncoder(), FileOutput(outputright))
except Exception as e:
    print("Right")    
    print(e)
    picam2right = None
    outputright = None

print(picam2left)
print(picam2right)
    
if picam2left != None:
    picam2left.start_recording(JpegEncoder(), FileOutput(outputleft))
    if picam2right != None:
        picam2right.start_recording(JpegEncoder(), FileOutput(outputright))
    try:
        address = ('', 8000)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        picam2left.stop_recording()
        if picam2right != None:
            picam2right.stop_recording()
else:
    print(picam2left)


