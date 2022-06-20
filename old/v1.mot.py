from operator import le
import cv2
import os
import numpy
import time
import requests
import datetime
from PIL import Image
from subprocess import Popen, PIPE
import imutils
import sys


""" Constant Variables """
input_fps = 20
resize_height = 720
blur_size = 15
pts = numpy.array([[2,389],[713,295],[949,334],[960,720],[143,692],[2,389]])
samples_per_minute = 240
difference_threshold = 8
min_area = 100
max_area = 999999
dilate_iterations = 2
numAreas = 6   #how many samples to smooth the average area
perc_screen_threshold = 0.015
do_dilate = True
do_blur = True
do_mask = True
do_blobdetect = False

""" blob detector params"""

params = cv2.SimpleBlobDetector_Params()
params.filterByColor = False
params.filterByArea = True
params.minArea = 100
params.filterByCircularity = False
params.filterByConvexity = False
params.filterByInertia = False

""" replace constants if arguments passed in"""

if len(sys.argv) > 1:
        if sys.argv[1] == 'F':
                do_dilate = False
else:
        print('Usage: <script> [T/F dilation] [T/F Blur] [samples/sec] [T/F Mask] [dilate iterations] [diff threshold] [(must be odd)blur size] [min area] [trigger threshold]')
        exit()
if len(sys.argv) > 2:
        if sys.argv[2] == 'F':
                do_blur = False
if len(sys.argv) > 3:
        samples_per_minute = int(sys.argv[3])*60
if len(sys.argv) > 4:
        if sys.argv[4] == 'F':
                do_mask = False
if len(sys.argv) > 5:
        dilate_iterations = int(sys.argv[5])
if len(sys.argv) > 6:
        difference_threshold = int(sys.argv[6])
if len(sys.argv) > 7:
        blur_size = int(sys.argv[7])
if len(sys.argv) > 8:
        min_area = int(sys.argv[8])
if len(sys.argv) > 9:
        perc_screen_threshold = int(sys.argv[9])

logfile = "/tmp/record/log"
in_filename = ""
path = "/tmp/record"
go = True
#f = open(logfile,"a")

def process_frame(in_frame):
        resi = cv2.resize(in_frame,(int(resize_height/frame_height*frame_width),resize_height))
        mask = numpy.zeros(resi.shape[:2],numpy.uint8)
        cv2.drawContours(mask,[pts],-1,(255,255,255),-1,cv2.LINE_AA)
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

def mot_scan(fileCount,name):
        trigger = False
        frame_count = 0
        samples = input_fps / int(samples_per_minute/60)
        percScreen = 0
        areaIndex = 0
        subtot = 0
        maxAve = 0
        tot = 0
        ave = 0
        areas = []
        areas = [0 for i in range(numAreas)]
        ret, frame = cap.read()
        frame_count = frame_count + 1
        gray = process_frame(frame)
        #p = Popen(['ffmpeg','-y','-f','image2pipe','-vcodec','bmp','-r',str(samples_per_minute/60),'-i','-','-vcodec','h264','-preset','ultrafast','-crf','32','-r',str(samples_per_minute/60),'out'+'-'+str(fileCount)+name+'.mp4'],stdin=PIPE)
        while ret:
                while frame_count < samples:
                        ret, frame = cap.read()
                        frame_count = frame_count + 1
                frame_count = 0
                if ret == False:
                        break
                gray0 = gray
                gray = process_frame(frame)
                subtot, dilated, cnts, b_o_m, b_u_m = diff_subtot_area(gray0,gray)

                """smooth area readings"""
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
        cap.release()
        return trigger

        """
        if trigger == True:
                newname = str(int(datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=-6))).timestamp())) \
                        + '_6-967003_bssnopark_200-200-400-400_24_769' \
                        + '.mp4'
                os.rename(testfile,path+"/"+newname)
                with open(path+"/"+newname,'rb') as payload:
                        headers = {'Content-Type': 'application/json', \
                                'X-Kerberos-Storage-FileName': newname, \
                                'X-Kerberos-Storage-Capture':'ab', \
                                'X-Kerberos-Storage-Device':'bssnopark', \
                                'X-Kerberos-Storage-AccessKey':'jmbP2rpqvkxAG3I8', \
                                'X-Kerberos-Storage-SecretAccessKey':'hX02vCeR6T9@m67IB82g0Rhx6V', \
                                'X-Kerberos-Storage-Provier':'cephProvider', \
                                'X-Kerberos-Storage-Directory':'tmerril7' \
                        }
                        r = requests.post('https://api.vault.tnstlab.com/storage',data=payload,headers=headers)
                        print(str(r.status_code)+':'+ str(r.content))
                        if r.status_code == 200:
                                os.remove(path+'/'+newname)
                                f = open(logfile,"a") 
                                f.write('Success :'+newname)
                                f.close()
                        else:
                                f = open(logfile,"a") 
                                f.write('failed :'+newname)
                                f.close()
        else:
               
                os.remove(testfile)
                #os.rename(testfile,path+"/"+"no_mot"+in_filename)
                """

fsize = 0
selectedName = ''
num_files = 1
while go:                
        with os.scandir(path) as it:

                #get file count in process folder
                """
                num_files = 0
                with os.scandir(path) as it2:
                        for entry in it2:
                                if entry.name.startswith('test'):
                                        num_files = num_files + 1
                """
                #this block goes for the oldest file

                selectedName = ''
                oldestTime = 0
                for entry in it:
                        if entry.name.startswith('new'):
                                if oldestTime == 0:
                                    oldestTime = os.stat(path+'/'+entry.name).st_mtime
                                    selectedName = path+'/'+entry.name
                                else: 
                                        if os.stat(path+'/'+entry.name).st_mtime - oldestTime < 0:
                                                oldestTime = os.stat(path+'/'+entry.name).st_mtime
                                                selectedName = path+'/'+entry.name


                if selectedName != '':
                        fSize = os.stat(selectedName).st_size
                        print('\033[2K\r{}'.format(fSize),end='')
                        while True:
                                time.sleep(3)
                                print('\033[2K\r{}'.format(os.stat(selectedName).st_size),end='')
                                if fSize == os.stat(selectedName).st_size:
                                        global cap
                                        cap = cv2.VideoCapture(fullName)
                                        global frame_height
                                        global frame_width
                                        frame_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                                        frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                                        mot_scan(selectedName)
                                        break
                                else:
                                        fSize = os.stat(selectedName).st_size
                else:
                        print('\033[2K\r'+'no files to process',end='')
                        time.sleep(10)
       

""" #f.close()


# ffmpeg -rtsp_transport tcp -i "rtsp://admin:admin@10.0.72.15/defaultPrimary?streamType=u" -vcodec copy -an -f segment -segment_time 10 -reset_timestamps 1 -strftime 1 "/tmp/record/new_%j-%H.%M.%S.mp4"
# docker run --rm --name opencv -d -v /home/travis/data/opencv/nfs:/ext tramer/pyth-opencv
# mongo ::::   NumberLong(1654273008    db.media.find({timestamp:NumberLong(1654273008)},{filename:1,_id:0})


#os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'

#def Receive():
#       print("start receive")
#       global frame_width
#       global frame_height
#       frame_width = int(cap.get(3))
#       frame_height = int(cap.get(4))
#       ret, frame = cap.read()
#       q.put(frame)
#       while ret:
#               ret, frame = cap.read()
#               q.put(frame)
#       cap.release()

#def Write():
#       print("Start Write")
#       print(frame_width)
#       print(frame_height)
#       out = cv2.VideoWriter('/ext/outpy.mp4',cv2.VideoWriter_fourcc('m','p','4','v'), 20.0, (frame_width,frame_height))
#       while True:
#               if q.empty() !=True:
#                       frame=q.get()
#                       out.write(frame)
#       out.release()
#
#
#
#if __name__=='__main__':
#       p1=threading.Thread(target=Receive)
#       p2=threading.Thread(target=Write)
#       p1.start()
#       p2.start()

#timeout = time.time() + 10

#while (True):
#       if ret == True:
#               out.write(frame)
#               if time.time() > timeout:
#                       break
#       else:
#               break """
