import os

import numpy
import cv2.cv as cv

locations = [
"D:/Users/Jonathan/Desktop/opencv/samples/python2/video/recs/yoni/rgb",
"/spaceil/geekcon2012/video/recs/yoni/rgb"
]

for location in locations:
    if os.path.exists(location):
        file_template = '%s/%%05d' % location
        break
else:
    print "missing rgb images directory, not any of %s" % repr(locations)
    raise SystemExit

file_frame = 0
def read_one_frame():
    global file_frame
    filename = file_template % file_frame
    file_frame += 1
    with open(filename, 'rb') as fd:
        s = fd.read()
    #assert(len(s) == 720 * 480 * 3)
    return numpy.fromstring(s, dtype=numpy.uint8).reshape(480,720,3)

class FakeCam(object):
    def read(self):
        " ret status, frame (numpy array)"
        return True, read_one_frame()

if __name__ == '__main__':
    read_one_frame()
