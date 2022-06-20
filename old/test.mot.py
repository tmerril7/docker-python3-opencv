import cv2
import os
import numpy
import time
import requests
import datetime
from PIL import Image
from subprocess import Popen, PIPE
import imutils


""" Constant Variables """
resize_height = 720
blur_size = 15
pts = numpy.array([[2,389],[713,295],[949,334],[960,720],[143,692],[2,389]])
samples_per_minute = 60
difference_threshold = 9
min_area = 10
max_area = 999999
dilate_iterations = 4
numAreas = 20
perc_screen_threshold = 0.015

logfile = "/tmp/record/log"
in_filename = ""
path = "/tmp/test"
go = True
#f = open(logfile,"a")

def process_frame(in_frame):
        resi = cv2.resize(in_frame,(int(resize_height/frame_height*frame_width),resize_height))
        mask = numpy.zeros(resi.shape[:2],numpy.uint8)
        cv2.drawContours(mask,[pts],-1,(255,255,255),-1,cv2.LINE_AA)
        dst = cv2.bitwise_and(resi,resi,mask=mask)
        blur = cv2.GaussianBlur(dst,(blur_size,blur_size),0)
        gray = cv2.cvtColor(blur,cv2.COLOR_BGR2GRAY)
        return gray

def diff_subtot_area(gray0,gray):
        diff = cv2.absdiff(gray0,gray)
        thresh = cv2.threshold(diff,difference_threshold,255,cv2.THRESH_BINARY)[1]
        dilated = cv2.dilate(thresh,None,iterations=dilate_iterations)
        cnts = cv2.findContours(dilated.copy(),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        subtot = 0
        for c in cnts:
                subtot = subtot + cv2.contourArea(c)
        
        return subtot, dilated, cnts

def mot_scan(fileCount):
        trigger = False
        frame_count = 0
        samples = int(samples_per_minute/60*20)
        numCnts = 0
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
        p = Popen(['ffmpeg','-y','-f','image2pipe','-vcodec','bmp','-r','20','-i','-','-vcodec','h264','-preset','ultrafast','-crf','32','-r','20','out'+'-'+str(fileCount)+'.mp4'],stdin=PIPE)
        while ret:
                while frame_count < samples:
                        ret, frame = cap.read()
                        frame_count = frame_count + 1
                frame_count = 0
                if ret == False:
                        break
                gray0 = gray
                gray = process_frame(frame)
                subtot, dilated, cnts = diff_subtot_area(gray0,gray)

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
                dilated = cv2.putText(dilated, "area: {:.1%}".format(percScreen),(10,20),cv2.FONT_HERSHEY_SIMPLEX, 1, (255,200,255),1)
                dilated = cv2.putText(dilated,"bodies: {}".format(len(cnts)),(10,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),1)
                im = Image.fromarray(dilated)
                im.save(p.stdin, 'bmp')
        p.stdin.close()
        p.wait()
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
fileCount = 0
while go:
        with os.scandir(path) as it:
                selectedName = ''
                oldestTime = 0
                for entry in it:
                        if entry.name.startswith('test'):
                                if oldestTime == 0:
                                        oldestTime = os.stat(path+'/'+entry.name).st_mtime
                                        selectedName = entry.name
                                else: 
                                        if os.stat(path+'/'+entry.name).st_mtime - oldestTime < 0:
                                                oldestTime = os.stat(path+'/'+entry.name).st_mtime
                                                selectedName = entry.name
        if selectedName != '':
                fileCount = fileCount + 1
                fullName = path+'/'+str(fileCount)+'.'+selectedName
                os.rename(path+'/'+selectedName,fullName)
                global cap
                cap = cv2.VideoCapture(fullName)
                global frame_height
                global frame_width
                frame_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                mot_scan(fileCount)


        else:
                print('\033[2K\r'+'no more files to process',end='')
                break

""" #f.close()


# ffmpeg -rtsp_transport tcp -i "rtsp://admin:admin@10.0.72.15/defaultPrimary?streamType=u" -vcodec copy -an -f segment -segment_time 10 -reset_timestamps 1 -strftime 1 "/tmp/record/new_%j-%H.%M.%S.mp4"
# docker run --rm --name opencv -d -v /home/travis/data/opencv/nfs:/ext tramer/pyth-opencv

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
