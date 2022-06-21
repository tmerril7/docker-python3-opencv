#V2.2
import av
import av.datasets
import cv2
import os
import numpy
import time
import requests
import datetime
from PIL import Image
from subprocess import Popen, PIPE
import imutils
import pymongo
import shutil
import argparse
import logging
from logging.handlers import RotatingFileHandler

#logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s')

def create_rotating_log(path):
        global logger
        logger = logging.getLogger("Rotating Log")
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(path, maxBytes=500000, backupCount=4)
        formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

loggerFile = '/var/log/motion.log'
create_rotating_log(loggerFile)

""" Constant Variables """
refresh_mongo_time = 5.0 * 60.0
input_fps = 20
resize_height = 720
blur_size = 15
pts = []
samples_per_minute = 240
difference_threshold = 8
min_area = 100
max_area = 25000
dilate_iterations = 2
numAreas = 5   #how many samples to smooth the average area
perc_screen_threshold = 0.015
do_dilate = True
do_blur = True
do_mask = True
do_blobdetect = False
maxPercInc = 0.1
heartBeatInterval = 60  # in seconds
upDays = 1
startTime = int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp())
lastHeartBeat = 0
use_new_ffmpeg_read = True

""" blob detector params"""

params = cv2.SimpleBlobDetector_Params()
params.filterByColor = False
params.filterByArea = True
params.minArea = 100
params.filterByCircularity = False
params.filterByConvexity = False
params.filterByInertia = False

""" replace constants if arguments passed in"""

parser = argparse.ArgumentParser(description='start motion detector')
parser.add_argument('cameraName',type=str, metavar='CameraName',help='name of camera')
parser.add_argument('mongoUser',type=str,help='mongodb username')
parser.add_argument('mongoPass',type=str,help='mongodb password')
args = parser.parse_args()
cameraName = args.cameraName
      
mongoUser = args.mongoUser
mongoPassword = args.mongoPass
mongoUrl = "@cluster0.pkex7.mongodb.net/?retryWrites=true&w=majority"

client = pymongo.MongoClient("mongodb+srv://" + mongoUser + ":" + mongoPassword + mongoUrl)
db = client.motionDetection

def update_mongo():
        global mongo_vars
        mongo_vars = db.cameras.find_one({'cameraName':cameraName},{'_id':0})
        while mongo_vars == None:
                '''
                print(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).strftime('%b %d, %Y - %H:%M: ')\
                + "can't find camera in database",end='\r')
                '''
                logger.warning(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).strftime('%b %d, %Y - %H:%M: ')\
                + "can't find camera in database")
                time.sleep(10)
                mongo_vars = db.cameras.find_one({'cameraName':cameraName},{'_id':0})
        try:
                while mongo_vars['disabled'] == True:
                        logger.info(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).strftime('%b %d, %Y - %H:%M: ')\
                        + "camera is disabled")
                        time.sleep(refresh_mongo_time)
                        mongo_vars = db.cameras.find_one({'cameraName':cameraName},{'_id':0})
        except:
                pass
        global key
        key = mongo_vars['key']
        global secretKey
        secretKey = mongo_vars['secretKey']
        global deviceName
        deviceName = mongo_vars['deviceName']
        global hubKey
        hubKey = mongo_vars['hubKey']
        global hubUser
        hubUser = mongo_vars['hubUser']
        global do_dilate
        do_dilate = mongo_vars['do_dilate']
        global do_blur
        do_blur = mongo_vars['do_blur']
        global samples_per_minute
        samples_per_minute = mongo_vars['samples_per_minute'] * 60
        global do_mask
        do_mask = mongo_vars['do_mask']
        global dilate_iterations
        dilate_iterations = mongo_vars['dilate_iterations']
        global difference_threshold
        difference_threshold = mongo_vars['difference_threshold']
        global blur_size
        blur_size = mongo_vars['blur_size']
        global min_area
        min_area = mongo_vars['min_area']
        global perc_screen_threshold
        perc_screen_threshold = mongo_vars['perc_screen_threshold']
        global pts
        pts = numpy.array(mongo_vars['mask'])
        global last_mongo_update

        if len(mongo_vars['deviceName']) > 0:
                logger.info('done loading parameters from mongoDB')
                last_mongo_update = int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp())
                return True
        else:
                logger.warning('failed getting parameters from mongoDB')
                return False

last_mongo_update = 0

while update_mongo() == False:
        time.sleep(60)

def heartBeat():
        if int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp()) - startTime <= (60*60*24):
                uptimeStr = 'up 1 day'
        else:
                upDays = int((int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp()) - startTime) / (60*60*24))
                uptimeStr = 'up {} days'.format(upDays)

        hd = {"accept" : "application/json"}
        heartBeatURL = 'https://api.cloud.kerberos.io/devices/heartbeat'
        data = {
                "key" : mongo_vars['deviceName'],
                "version" : "8.0",
                "clouduser" : mongo_vars['hubUser'],
                "cloudpublickey" : mongo_vars['hubKey'],
                "cameraname" : mongo_vars['cameraName'],
                "cameratype" : "IPCamera",
                "docker" : True,
                "kios" : False,
                "raspberrypi" : False,
                "enterprise" : True,
                "uptime" : uptimeStr,
                "timestamp" : int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp())
        }
        a = requests.post(heartBeatURL,json=data,headers=hd)
        return a.status_code


in_filename = ""
path = "/ramdisk/"+cameraName
uploadPath = '/tmp/staging'

def process_frame(in_frame,makeThumb,makeMask):
        resi = cv2.resize(in_frame,(int(resize_height/frame_height*frame_width),resize_height))
        if makeThumb:
                im = Image.fromarray(cv2.cvtColor(resi, cv2.COLOR_BGR2RGB))
                im.save(path + '/' + 'thumb.jpg','jpeg')
                logger.info('created thumb.jpg')
        mask = numpy.zeros(resi.shape[:2],numpy.uint8)
        cv2.drawContours(mask,[pts],-1,(255,255,255),-1,cv2.LINE_AA)
        if makeMask:
                im = Image.fromarray(cv2.cvtColor(cv2.polylines(resi,[pts],True,(0,0,255),2), cv2.COLOR_BGR2RGB))
                #im = Image.fromarray(cv2.polylines(tmpFrame,pts,True,255,255,255))
                im.save(path + '/' + 'mask.jpg','jpeg')
                logger.info('created mask.jpg')
        if do_mask == True:
                dst = cv2.bitwise_and(resi,resi,mask=mask)
        else:
                dst = resi
        if do_blur == True:
                blur = cv2.GaussianBlur(dst,(blur_size,blur_size),0)
        else:
                blur = dst
        gray = cv2.cvtColor(blur,cv2.COLOR_BGR2GRAY)
        return gray

def diff_subtot_area(gray0,gray):
        diff = cv2.absdiff(gray0,gray)
        thresh = cv2.threshold(diff,difference_threshold,255,cv2.THRESH_BINARY)[1]
        if do_dilate == True:
                dilated = cv2.dilate(thresh,None,iterations=dilate_iterations)
        else:
                dilated = thresh
        cnts = cv2.findContours(dilated.copy(),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        subtot = 0
        bodies_over_min = 0
        bodies_under_min = 0
        for c in cnts:
                if cv2.contourArea(c) > min_area:
                        subtot = subtot + cv2.contourArea(c)
                        bodies_over_min = bodies_over_min + 1
                else:
                        bodies_under_min = bodies_under_min + 1
        return subtot, dilated, len(cnts), bodies_over_min, bodies_under_min

def mot_scan(name,thumb,mask):
        trigger = False
        makeThumb = not thumb
        makeMask = not mask
        frame_count = 0
        samples = input_fps / int(samples_per_minute/60)
        percScreen = 0
        areaIndex = 0
        subtot = 0
        prevSubtot = 0
        maxAve = 0
        tot = 0
        ave = 0
        areas = []
        areas = [0 for i in range(numAreas)]
        ret, frame = cap.read()
        frame_count = frame_count + 1
        gray = process_frame(frame,makeThumb,makeMask)

        #p = Popen(['ffmpeg','-y','-f','image2pipe','-vcodec','bmp','-r',str(samples_per_minute/60),'-i','-','-vcodec','h264','-preset','ultrafast','-crf','32','-r',str(samples_per_minute/60),'out'+'-'+str(fileCount)+name+'.mp4'],stdin=PIPE)
        while ret:
                while frame_count < samples:
                        ret, frame = cap.read()
                        frame_count = frame_count + 1
                frame_count = 0
                if ret == False:
                        break
                gray0 = gray
                gray = process_frame(frame,False,False)
                subtot, dilated, cnts, b_o_m, b_u_m = diff_subtot_area(gray0,gray)

                """smooth area readings"""
                if subtot > prevSubtot:
                        if subtot - prevSubtot > subtot * maxPercInc:
                                subtot = prevSubtot + subtot * maxPercInc
                tot = tot - areas[areaIndex]
                areas[areaIndex] = subtot
                tot = tot + areas[areaIndex]
                areaIndex = areaIndex + 1
                if areaIndex >= numAreas:
                        areaIndex = 0
                ave = tot / numAreas

                percScreen = ave / (frame_height * frame_width)
                if percScreen > maxAve:
                        maxAve = percScreen
                if percScreen >= perc_screen_threshold:
                        trigger = True
                        break
                
                prevSubtot = subtot
                #dilated = cv2.putText(dilated, "area: {:.3%}".format(percScreen),(10,20),cv2.FONT_HERSHEY_SIMPLEX, 1, (255,200,255),1)
                #dilated = cv2.putText(dilated,"bodies: {}".format(cnts) + ' ({}/'.format(b_u_m) + '{})'.format(b_o_m),(10,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),1)
                """
                if do_blobdetect:
                        detector = cv2.SimpleBlobDetector_create(params)
                        keypoints = detector.detect(dilated)
                        im_with_keypoints = cv2.drawKeypoints(dilated,keypoints,numpy.array([]),(255,0,0),cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
                        im = Image.fromarray(im_with_keypoints)
                        im.save(p.stdin,'bmp')
                else:
                        im = Image.fromarray(dilated)
                        im.save(p.stdin, 'bmp')
                """
        #p.stdin.close()
        #p.wait()
        if not use_new_ffmpeg_read:
            cap.release()
        return trigger, maxAve

def mot_scan_lib_av(name,thumb,mask):
        trigger = False
        makeThumb = not thumb
        makeMask = not mask
        frame_count = 0
        samples = input_fps / int(samples_per_minute/60)
        percScreen = 0
        areaIndex = 0
        subtot = 0
        prevSubtot = 0
        maxAve = 0
        tot = 0
        ave = 0
        areas = []
        areas = [0 for i in range(numAreas)]
        global frame_height
        global frame_width
        frame_height = 0
        frame_width = 0
        try:
            container = av.open(av.datasets.curated(name))
        except:
            logger.error('something bad happened')
            return trigger, maxAve
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"

        first_pass = True
        #p = Popen(['ffmpeg','-y','-f','image2pipe','-vcodec','bmp','-r',str(samples_per_minute/60),'-i','-','-vcodec','h264','-preset','ultrafast','-crf','32','-r',str(samples_per_minute/60),'out'+'-'+str(fileCount)+name+'.mp4'],stdin=PIPE)
        for decoded_frame in container.decode(stream):
            if first_pass:
                frame_height = decoded_frame.height
                frame_width = decoded_frame.width
                gray = process_frame(decoded_frame.to_ndarray(format="bgr24"),makeThumb,makeMask)
                first_pass = False
                frame_count = frame_count + 1
                continue
            if frame_count < samples:
                frame_count = frame_count + 1
                continue
            else:
                frame_count = 0
            gray0 = gray
            gray = process_frame(decoded_frame.to_ndarray(format="bgr24"),False,False)
            subtot, dilated, cnts, b_o_m, b_u_m = diff_subtot_area(gray0,gray)

            """smooth area readings"""
            if subtot > prevSubtot:
                    if subtot - prevSubtot > subtot * maxPercInc:
                            subtot = prevSubtot + subtot * maxPercInc
            tot = tot - areas[areaIndex]
            areas[areaIndex] = subtot
            tot = tot + areas[areaIndex]
            areaIndex = areaIndex + 1
            if areaIndex >= numAreas:
                    areaIndex = 0
            ave = tot / numAreas

            percScreen = ave / (frame_height * frame_width)
            if percScreen > maxAve:
                    maxAve = percScreen
            if percScreen >= perc_screen_threshold:
                    trigger = True
                    break
            
            prevSubtot = subtot
            #dilated = cv2.putText(dilated, "area: {:.3%}".format(percScreen),(10,20),cv2.FONT_HERSHEY_SIMPLEX, 1, (255,200,255),1)
            #dilated = cv2.putText(dilated,"bodies: {}".format(cnts) + ' ({}/'.format(b_u_m) + '{})'.format(b_o_m),(10,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),1)
            """
            if do_blobdetect:
                    detector = cv2.SimpleBlobDetector_create(params)
                    keypoints = detector.detect(dilated)
                    im_with_keypoints = cv2.drawKeypoints(dilated,keypoints,numpy.array([]),(255,0,0),cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
                    im = Image.fromarray(im_with_keypoints)
                    im.save(p.stdin,'bmp')
            else:
                    im = Image.fromarray(dilated)
                    im.save(p.stdin, 'bmp')
            """
        #p.stdin.close()
        #p.wait()
        container.close()
        return trigger, maxAve

#fsize = 0
#selectedName = ''
#num_files = 1
while True:
        with os.scandir(path) as it:
                thumb_exists = False
                mask_exists = False
                selectedName = ''
                oldestTime = 0
                for entry in it:
                        if entry.name == 'thumb.jpg':
                                thumb_exists = True
                        if entry.name == 'mask.jpg':
                                mask_exists = True
                        if entry.name.startswith('new'):
                                if oldestTime == 0:
                                    oldestTime = os.stat(entry.path).st_mtime
                                    selectedName = entry.path
                                else: 
                                        if os.stat(entry.path).st_mtime - oldestTime < 0:
                                                oldestTime = os.stat(entry.path).st_mtime
                                                selectedName = entry.path
        if selectedName != '':
                fSize = os.stat(selectedName).st_size
                print('\033[2K\r{}'.format(fSize),end='')
                while True:
                        time.sleep(3)
                        print('\033[2K\r{}'.format(os.stat(selectedName).st_size),end='')
                        if fSize == os.stat(selectedName).st_size:
                            if not use_new_ffmpeg_read:
                                #global trigger
                                #global maxAve
                                #global cap
                                cap = cv2.VideoCapture(selectedName)
                                #global frame_height
                                #global frame_width
                                frame_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                                frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                                if frame_height <=1:
                                        logger.warning('failed Div 0: '+ selectedName)
                                        trigger = False
                                        maxAve = 0
                                        break
                                start_stopwatch = time.time()
                                trigger, maxAve = mot_scan(selectedName,thumb_exists,mask_exists)
                                duration = time.time() - start_stopwatch
                                logger.info('time to run motion scan: {:.3}'.format(duration))
                                break
                            else:
                                start_stopwatch = time.time()
                                trigger, maxAve = mot_scan_lib_av(selectedName,thumb_exists,mask_exists)
                                duration = time.time() - start_stopwatch
                                logger.info('time to run motion scan: {:.3}'.format(duration))
                                break
                        else:
                                fSize = os.stat(selectedName).st_size
                logger.info(' '+str(trigger)+' {:.5f}'.format(maxAve)+' {} {}'.format(frame_width,frame_height))
                if trigger == True:
                        newname = uploadPath + '/' \
                                + str(int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp())) \
                                + '_6-967003_' \
                                +cameraName \
                                +'_200-200-400-400_24_769' \
                                + '.mp4'
                        try:
                                shutil.copy2(selectedName,newname)
                                os.remove(selectedName)
                        except:
                                continue
                else:
                        os.remove(selectedName)
        else:
                print('\033[2K\r'+'no files to process',end='')
                time.sleep(10)

                #  periodic mongodb refresh
        if int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp()) - int(last_mongo_update) >= int(refresh_mongo_time):
                logger.info('refreshing mongodb at {}'.format(str(int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp()))))
                while update_mongo() == False:
                        time.sleep(60)

                # periodic hearbeat
        if int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp()) - int(lastHeartBeat) >= int(heartBeatInterval):
                logger.info('sending heartbeat at {}'.format(str(int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp()))))
                if heartBeat() == 200:
                        logger.info('heartBeat success')
                        lastHeartBeat = int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp())
                else:
                        logger.warning('problem sending hearbeat')
        
        


# ffmpeg -rtsp_transport tcp -i "rtsp://admin:admin@10.0.72.20/defaultPrimary?streamType=u" -vcodec copy -an -f segment -segment_time 10 -reset_timestamps 1 -strftime 1 "/ramdisk/bssno-gate/new_%j-%H.%M.%S.mp4"
# docker run --rm --name opencv-c1 -d -v /ramdisk:/ramdisk -v /home/travis/data/opencv/nfs:/ext -v /tmp/staging:/tmp/staging tramer/pyth-opencv
# mongo ::::   NumberLong(1654273008    db.media.find({timestamp:NumberLong(1654273008)},{filename:1,_id:0})
