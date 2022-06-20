import subprocess
import shlex
import argparse
import os
import time
import pymongo
import datetime

basepath = '/ramdisk'

parser = argparse.ArgumentParser(description='start ffmpeg to record rtsp stream in segments')
parser.add_argument('cameraName',type=str, metavar='CameraName',help='name of camera')
parser.add_argument('mongoUser',type=str,help='mongodb username')
parser.add_argument('mongoPass',type=str,help='mongodb password')

args = parser.parse_args()
mongoUrl = "@cluster0.pkex7.mongodb.net/?retryWrites=true&w=majority"
client = pymongo.MongoClient("mongodb+srv://" + args.mongoUser + ":" + args.mongoPass + mongoUrl)
db = client.motionDetection

mongoVars = db.cameras.find_one({'cameraName':args.cameraName},{'_id':0})

while mongoVars == None:
    print(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).strftime('%b %d, %Y - %H:%M: ')\
    + "can't find camera in database",end='\r')
    time.sleep(10)
    mongoVars = db.cameras.find_one({'cameraName':args.cameraName},{'_id':0})
while True:
    try: 
        testURL = mongoVars['rtspURL']
        break
    except:
        print(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).strftime('%b %d, %Y - %H:%M: ')\
        + "no rtspURL in database for this camera",end='\r')
        time.sleep(10)
        mongoVars = db.cameras.find_one({'cameraName':args.cameraName},{'_id':0})
        

d = shlex.split("ffmpeg -rtsp_transport tcp -stimeout 5000000 -use_wallclock_as_timestamps 1 -i '" + \
    mongoVars['rtspURL'] + \
    "' -vcodec copy -an -f segment -segment_time 10 -reset_timestamps 1 -strftime 1 '/ramdisk/" + \
    args.cameraName + \
    "/new_%j-%H.%M.%S.mp4'")



while True:
    time.sleep(1)
    try:
        print('###starting###')
        
        if not os.path.isdir(basepath + '/' + args.cameraName):
            os.mkdir(basepath + '/' + args.cameraName)
        time.sleep(3)
        with os.scandir(basepath + '/' + args.cameraName) as it:
            count = 0
            for name in it:
                count = count + 1
            if count > 12:
                print('file buffer full - restarting')
                continue
    except:
        print('problem occurred')
        continue
    sp = subprocess.Popen(d)
    while True:
        try:
            time.sleep(5)
            if sp.returncode != None:
                break
            if sp.poll() != None:
                break
            with os.scandir(basepath + '/' + args.cameraName) as it:
                count = 0
                for name in it:
                    count = count + 1
                if count > 12:
                    sp.terminate()
                    break
        except:
            print('crashed')
            sp.terminate()
            break
    sp.wait()
    if sp.returncode == 0:
        print(sp.returncode)
    if sp.returncode != 0:
        print('it broke')
        print(sp.returncode)
