from Modules import FaceRender,Camera,Delay
import cv2
import time
import argparse
import pyfakewebcam
import numpy as np
from prettytable import PrettyTable 
from multiprocessing import Process, Queue

ArgParser = argparse.ArgumentParser()
   
ArgParser.add_argument("-c","--camera",   type=int, default=0,    help="Device number of the camera to use")
ArgParser.add_argument("-o","--output",   type=int, default=None, help="Device number of the camera to output")
ArgParser.add_argument("-f","--fps",      type=int, default=30,   help="Frames per second of the video")
ArgParser.add_argument("-r","--rotation", type=int, default=0,    help="Rotation of the camera in 90\u00B0 increments.")
ArgParser.add_argument("-d","--downscale",type=int, default=2,    help="How much to downscale the video before calculations, lower is faster but less accurate")
ArgParser.add_argument("-b","--buffer",   type=int, default=2,    help="Buffer size for facial detection, helps to reduce jitter but increases latency")
ArgParser.add_argument("-s","--show",     type=bool,default=False,help="Display the live camera feed")
args =  vars(ArgParser.parse_args())


DEVICE = Camera.CaptureDevice(args['camera'],
    fps=args['fps'],
    rotation=args["rotation"],
    show=args['show']
    )

DOWNSCALE = args["downscale"]
FRAMEBUFFER = args["buffer"]
if args["output"]:
    FAKEWEBCAM = pyfakewebcam.FakeWebcam(f'/dev/video{args["output"]}',DEVICE.WIDTH,DEVICE.HEIGHT)

def CaptureFaceLandmarks(queue:Queue):
    Timer = Delay.Timer(DEVICE.FRAMETIME)
    while DEVICE.ENABLE:
        image = DEVICE.image
        FaceCalculation = FaceRender.Calculate(image=image,downscale=DOWNSCALE)
        if FaceCalculation:
            if queue.full():
                queue.get()
            queue.put(FaceCalculation)
        Timer()


q = Queue(FRAMEBUFFER)
p = Process(target=CaptureFaceLandmarks, args=(q,))
p.start()
print("Detecting Face...")
Frames = [q.get(),q.get()]

Timer = Delay.Timer(DEVICE.FRAMETIME)
frameTypes = [' ' for x in range(DEVICE.FPS)]
frameTimes = [ 0  for x in range(DEVICE.FPS)]
print("\033[s") # Saves cursor position
while DEVICE.ENABLE and cv2.waitKey(1000//DEVICE.FPS):
    print("\033[u") # Loads cursor position
    start = time.time()
    
    # Face Generation
    if q.empty(): # If no face is detected
        type = 'I' # Type is interpolated
        face = FaceRender.Interpolate(*Frames) # Interpolate
        Frames[0] = face # Set old face to interpolaed
        # This is done so that the interpolation target is the same
    else:
        type = 'P'
        face = q.get() # Get calculation from queue
        Frames[0] = Frames[1] # Set new frame as old frame
        Frames[1] = face # Set face as new frame

    image = FaceRender.Render(face,res=DEVICE.RESOLUTION) # Render frame
    if args["output"]:
        FAKEWEBCAM.schedule_frame(image) # Put frame on webcam
    else:
        cv2.imshow('Render',image) # Display frame

    # --------------- Stats -------------- #
    # Interpolation Ration
    frameTypes.insert(0,type)
    frameTypes.pop(len(frameTypes) - 1)
    InterpRation = frameTypes.count('I') / DEVICE.FPS
    
    # Frame Timing
    frametime = (time.time() - start)*1000
    frameTimes.pop(0)
    frameTimes.append(frametime)
    avgFrameTime = np.mean(frameTimes)

    # Creating Table
    StatTable = PrettyTable(["Name","Data"])
    StatTable.junction_char = "\u2543"
    StatTable.horizontal_char = "\u2501"
    StatTable.vertical_char = "\u2503"
    StatTable.add_rows((
            (    'Resolution:' ,f"{DEVICE.WIDTH},{DEVICE.HEIGHT}"),
            (           'FPS:' ,f"{DEVICE.FPS}"),
            (  'Frame Source:' ,''.join(frameTypes)),
            ('',''),
            (  'Interp Ratio:' ,f"{InterpRation:.2f}"),
            (    'Frame Time:' ,f"{frametime:.2f} ms"),
            ('Avg Frame Time:' ,f"{avgFrameTime:.2f} ms")
        ))
    print(StatTable)

    Timer()