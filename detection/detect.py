from operator import attrgetter
import numpy as np
from numpy import average
import cv2
import cv2.cv as cv
import readframe
import video
import copy
from common import nothing, clock, draw_str
from readframe import read_one_frame

MHI_DURATION = 0.5
DEFAULT_THRESHOLD = 32
MAX_TIME_DELTA = 0.25
MIN_TIME_DELTA = 0.05

import time
TRACKER_OK = 1
TRACKER_DEAD = 0
RELEVANT_NUMOF_HITS = 5
trackers=[]
CAPTURE_RADIUS_PX = 70
CAPTURE_RADIUS_PX_SQRD = CAPTURE_RADIUS_PX**2

class Tracker(object):
    TIME_WINDOW_SEC = 2
    @staticmethod
    def update_trackers(centers, rects):
        centers_to_rects = dict(zip(centers,rects))
        global trackers
        #print 'received %d centers' % len(centers)
        t=time.time()
        cutoff_time = t-Tracker.TIME_WINDOW_SEC
        kill_set = set()
        cx_cy_set = set()
        for tracker in trackers:
            if tracker.update(t, cutoff_time, centers, rects)==TRACKER_DEAD:
                kill_set.add(tracker)
            else:
                tracker_xy = (tracker.last_cx, tracker.last_cy)
                if tracker_xy in cx_cy_set:
                    kill_set.add(tracker)
                else:
                    cx_cy_set.add(tracker_xy)
        for tracker_to_kill in list(kill_set):
            trackers.remove(tracker_to_kill)
        new_cx_cy_list = list(set(centers)-cx_cy_set)
#        if len(new_cx_cy_list):
#            print 'adding %d trackers' % len(new_cx_cy_list)
        for new_cx, new_cy in new_cx_cy_list:
            trackers.append(Tracker(new_cx, new_cy, centers_to_rects[(new_cx, new_cy)]))
        trackers.sort(key=attrgetter('score'), reverse=True)

    last_cx = -1.0
    last_cy = -1.0
    hits = [] # list of hit time.time()

    def __init__(self, init_cx, init_cy, rect):
        self.last_cx=init_cx
        self.last_cy=init_cy
        self.rect = rect
    def update(self, t, cutoff_time, centers, rects):
        self.hits = [hit for hit in self.hits if hit>cutoff_time]
        for i,(cx,cy) in enumerate(centers):
            if (cx-self.last_cx)**2+(cy-self.last_cy)**2<CAPTURE_RADIUS_PX_SQRD:
                self.last_cx = cx
                self.last_cy = cy
                self.rect = rects[i]
                self.hits.append(time.time())
        return TRACKER_OK if len(self.hits) else TRACKER_DEAD

    @property
    def score(self):
        return len(self.hits)

def center_after_median_threshold(frame, rect):
    x, y, w, h = rect
    sub_rgb = frame[x:x+w, y:y+h, :]
    sub = np.sum(sub_rgb,axis=2)
    threshold = average(sub)
    for c in xrange(10):
        im_thresh = sub < (threshold * (c + 1) / 10)
        #print np.sum(im_thresh)
        if np.sum(im_thresh) > 20:
            break
    #print im_thresh.size, c, im_thresh
    yy, xx = np.indices(im_thresh.shape)
    #print im_thresh
    #print xx[im_thresh]
    #print yy[im_thresh]
    cx = average(xx[im_thresh])
    cy = average(yy[im_thresh])
    #print "mid", cx, cy
    return x + int(cx), y + int(cy)

def draw_motion_comp(vis, (x, y, w, h), angle, color):
    cv2.rectangle(vis, (x, y), (x+w, y+h), (0, 255, 0))
    r = min(w/2, h/2)
    cx, cy = x+w/2, y+h/2
    angle = angle*np.pi/180
    cv2.circle(vis, (cx, cy), r, color, 3)
    cv2.line(vis, (cx, cy), (int(cx+np.cos(angle)*r), int(cy+np.sin(angle)*r)), color, 3)

if __name__ == '__main__':
    import sys
    try: video_src = sys.argv[1]
    except: video_src = 0

    cv2.namedWindow('motempl')
    visuals = ['input', 'frame_diff', 'motion_hist', 'grad_orient']
    cv2.createTrackbar('visual', 'motempl', 2, len(visuals)-1, nothing)
    cv2.createTrackbar('threshold', 'motempl', DEFAULT_THRESHOLD, 255, nothing)

    #cam = video.create_capture(video_src, fallback='synth:class=chess:bg=../cpp/lena.jpg:noise=0.01')
    cam = readframe.FakeCam()
    ret, frame = cam.read()

    h, w = frame.shape[:2]
    prev_frame = frame.copy()
    motion_history = np.zeros((h, w), np.float32)
    hsv = np.zeros((h, w, 3), np.uint8)
    hsv[:,:,1] = 255
    while True:
        ret, frame = cam.read()
        frame_diff = cv2.absdiff(frame, prev_frame)
        gray_diff = cv2.cvtColor(frame_diff, cv2.COLOR_BGR2GRAY)
        thrs = cv2.getTrackbarPos('threshold', 'motempl')
        ret, motion_mask = cv2.threshold(gray_diff, thrs, 1, cv2.THRESH_BINARY)
        timestamp = clock()
        cv2.updateMotionHistory(motion_mask, motion_history, timestamp, MHI_DURATION)
        mg_mask, mg_orient = cv2.calcMotionGradient( motion_history, MAX_TIME_DELTA, MIN_TIME_DELTA, apertureSize=5 )
        seg_mask, seg_bounds = cv2.segmentMotion(motion_history, timestamp, MAX_TIME_DELTA)

        visual_name = visuals[cv2.getTrackbarPos('visual', 'motempl')]
        if visual_name == 'input':
            vis = frame.copy()
        elif visual_name == 'frame_diff':
            vis = frame_diff.copy()
        elif visual_name == 'motion_hist':
            vis = np.uint8(np.clip((motion_history-(timestamp-MHI_DURATION)) / MHI_DURATION, 0, 1)*255)
            vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
        elif visual_name == 'grad_orient':
            hsv[:,:,0] = mg_orient/2
            hsv[:,:,2] = mg_mask*255
            vis = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        centers = []
        rects = []
        for i, rect in enumerate([(0, 0, w, h)] + list(seg_bounds)):
            x, y, rw, rh = rect
            area = rw*rh
            if area < 64**2:
                continue
            silh_roi   = motion_mask   [y:y+rh,x:x+rw]
            orient_roi = mg_orient     [y:y+rh,x:x+rw]
            mask_roi   = mg_mask       [y:y+rh,x:x+rw]
            mhi_roi    = motion_history[y:y+rh,x:x+rw]
            if cv2.norm(silh_roi, cv2.NORM_L1) < area*0.05:
                continue
            angle = cv2.calcGlobalOrientation(orient_roi, mask_roi, mhi_roi, timestamp, MHI_DURATION)
            color = ((255, 0, 0), (0, 0, 255))[i == 0]
            draw_motion_comp(vis, rect, angle, color)
            centers.append( (x+rw/2, y+rh/2) )
            rects.append(rect)


        Tracker.update_trackers(centers, rects)
        #print 'Active trackers: %d' % len(trackers)
        #print 'Tracker score: %s' % ','.join(['%2d'%len(tracker.hits) for tracker in trackers])
        if len(trackers):
            first_tracker = trackers[0]
            x, y, rw, rh = first_tracker.rect
            cx, cy = center_after_median_threshold(frame, first_tracker.rect)
            color = (0,255,0) if len(first_tracker.hits)>=RELEVANT_NUMOF_HITS else (255,0,0)
            cv2.circle(vis, (cx, cy), 20, (0, 255, 0), 3)
            cv2.circle(vis, (cx, cy), CAPTURE_RADIUS_PX, (255, 0, 0), 1)
            for tracker in trackers[1:]:
                color = (0,255,0) if len(tracker.hits)>=RELEVANT_NUMOF_HITS else (0,0,255)
                cv2.circle(vis, (tracker.last_cx, tracker.last_cy), 10, color, 1)

        draw_str(vis, (20, 20), visual_name)
        cv2.imshow('motempl', vis)
        time.sleep(0.5)

        prev_frame = frame.copy()
        if 0xFF & cv2.waitKey(5) == 27:
            break
    cv2.destroyAllWindows() 			