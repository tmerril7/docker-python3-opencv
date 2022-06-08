import cv2
import os
import numpy
import time
import requests
import datetime
from PIL import Image
from subprocess import Popen, PIPE
import imutils
logfile = "/tmp/record/log"
in_filename = ""
path = "/tmp/record"
go = True
#f = open(logfile,"a")

def mot_scan(file):
        trigger = False
        pts = numpy.array([[2,389],[713,295],[949,334],[960,720],[143,692],[2,389]])
        numCnts = 0
        percScreen = 0
        areaIndex = 0
        numAreas = 20
        subtot = 0
        maxAve = 0
        tot = 0
        ave = 0
        areas = []
        areas = [0 for i in range(numAreas)]
        count = 0
        fps, duration = 24, 100
        #p = Popen(['ffmpeg','-y','-f','image2pipe','-vcodec','bmp','-r','20','-i','-','-vcodec','h264','-preset','ultrafast','-crf','32','-r','20','out.mp4'],stdin=PIPE)
        #for i in range(fps * duration):
        #       im = Image.new("RGB", (300,300),(i,1,1))
        #       im.save(p.stdin, 'JPEG')
        timeout = time.time() + 10
        #RTSP_URL = 'rtsp://admin:admin@10.0.72.15/defaultPrimary?streamType=u'
        testfile = file
        print('\033[2K\r'+testfile,end='')
        frame_width = 2048
        frame_height =1536
        #cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        cap = cv2.VideoCapture(testfile)
        ret, frame = cap.read()
        if isinstance(frame,numpy.ndarray):
                print('\033[2K\r'+'valid frame',end='')
        else:
                return
        count = count + 1
        resi = cv2.resize(frame,(960,720))
        mask = numpy.zeros(resi.shape[:2],numpy.uint8)
        cv2.drawContours(mask,[pts],-1,(255,255,255),-1,cv2.LINE_AA)
        dst = cv2.bitwise_and(resi,resi,mask=mask)
        blur = cv2.GaussianBlur(dst,(15,15),0)
        gray = cv2.cvtColor(blur,cv2.COLOR_BGR2GRAY)
        #gray0 = gray
        #im = Image.fromarray(gray)
        #im.save(p.stdin, 'JPEG')
        while ret:
                ret, frame = cap.read()
                if isinstance(frame,numpy.ndarray):
                        print('\033[2K\r' + 'valid frame',end='')
                else:
                        break
                count = count + 1
                gray0 = gray
                resi = cv2.resize(frame,(960,720))
                mask = numpy.zeros(resi.shape[:2],numpy.uint8)
                cv2.drawContours(mask,[pts],-1,(255,255,255),-1,cv2.LINE_AA)
                dst = cv2.bitwise_and(resi,resi,mask=mask)
                blur = cv2.GaussianBlur(dst,(15,15),0)
                gray = cv2.cvtColor(blur,cv2.COLOR_BGR2GRAY)
                diff = cv2.absdiff(gray0,gray)
                thresh = cv2.threshold(diff,9,255,cv2.THRESH_BINARY)[1]
                dilated = cv2.dilate(thresh,None,iterations=4)
                cnts = cv2.findContours(dilated.copy(),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                cnts = imutils.grab_contours(cnts)
                for c in cnts:
                        subtot = subtot + cv2.contourArea(c)
                tot = tot - areas[areaIndex]
                areas[areaIndex] = subtot
                subtot = 0
                tot = tot + areas[areaIndex]
                areaIndex = areaIndex + 1
                if areaIndex >= numAreas:
                        areaIndex = 0
                ave = tot / numAreas
                percScreen = ave / 86400
                #print('\033[2K\r{}'.format(percScreen),end='')
                if percScreen > maxAve:
                        maxAve = percScreen
                if percScreen >= 0.015:
                        trigger = True
                        break
                #cv2.threshold(cv2.absdiff(gray0,gray),40,255,cv2.THRESH_BINARY)
                dilated = cv2.putText(dilated, "area: {:.1%}".format(percScreen),(10,20),cv2.FONT_HERSHEY_SIMPLEX, 1, (255,200,255),1)
                dilated = cv2.putText(dilated,"bodies: {}".format(len(cnts)),(10,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),1)
                im = Image.fromarray(dilated)
                #im = Image.fromarray(frame)
        #        im.save(p.stdin, 'bmp')
                if count > 20 * 10:
                        break
        #p.stdin.close()
        #p.wait()
        print('\033[2K\r{:.3%}'.format(maxAve))
        cap.release()
        #f.write(testfile + ": {:.3%}".format(maxAve) + "\n")
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
doubleCheck = True
fsize = 0
selectedName = ''
while go:
        with os.scandir(path) as it:
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
                while doubleCheck:
                        time.sleep(3)
                        print('\033[2K\r{}'.format(os.stat(selectedName).st_size),end='')
                        if fSize == os.stat(selectedName).st_size:
                                print('\033[2K\r' + selectedName,end='')
                                mot_scan(selectedName)
                                break
                        else:
                                fSize = os.stat(selectedName).st_size
        else:
                print('\033[2K\r'+'no files to process',end='')
                time.sleep(10)
#f.close()
#q=queue.Queue()

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
#               break