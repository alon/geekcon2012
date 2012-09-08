#!/usr/bin/env python

"""
To run with firewire camera, you need to make sure the permissions are correct
on the device files.
"""

from __future__ import with_statement

debug = True

import time
import datetime
from multiprocessing import Process, Queue

import ctypes
import numpy

import cv

import sys, os
import gobject

gobject.threads_init()

import pygtk, gtk
import pygst
pygst.require("0.10")

# Do it early to avoid xcb assertions
#gtk.gdk.threads_init()

# don't let gst handle the --help for us
import sys
sargs = set(sys.argv)

import gst

from detection.detect import VideoTracker
if debug:
    import fake_motor as motor
else:
    import motor
import joystick
if debug:
    import fake_trigger as trigger
else:
    import trigger

def get_options():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-n', '--noaction', dest='noaction', help="don't actually do anything with the image - just show the camera picture", action='store_true')
    parser.add_option('-t', '--test', dest='test', help="use videotestsrc", action='store_true')
    opts, args = parser.parse_args()
    return opts

from video.inverseelement import FunElement

color=0

def gradient_cv_test(b):
    global color
    #print repr(b)
    color = (1 + color) % 256
    #rgb = cv.fromarray(b)
    rgb = cv.CreateMat(720, 480, cv.CV_8UC3)
    cv.Set(rgb, (color, color, color))
    s = rgb.tostring()
    # '\x80'*(720*480*3)
    return gst.Buffer(numpy.fromstring(s, dtype=numpy.uint8))

def test_image(width=4, height=4):
    return cv.fromarray(numpy.fromstring('0'*3*width*height, dtype=numpy.uint8
                       ).reshape(width, height, 3))

def test_generic(func):
    return func(imp)

def test_filter():
    return test_generic(filter)

def filter(inp):
    lapl = cv.CreateMat(inp.rows, inp.cols, cv.CV_8UC3)
    #lapl = cv.CreateImage((inp.rows, inp.cols), 32, 1)
    m = cv.CreateMat(3, 3, cv.CV_8UC1)
    m[0, 0] = 0
    m[0, 1] = 0
    m[0, 2] = 0
    m[2, 0] = -1
    m[2, 1] = -1
    m[2, 2] = -1
    m[1, 0] = -1
    m[1, 2] = -1
    m[1, 1] = 5
    cv.Filter2D(inp, lapl, m)
    return lapl

class Averager(object):
    def __init__(self, width=720, height=480):
        # accumulator must be 32F or 64F, can't be 8U
        self.acc = cv.CreateMat(width, height, cv.CV_32FC3)
    def filter(self, inp):
        cv.RunningAvg(inp, self.acc, 0.1)
        #return self.acc
        cv.Convert(self.acc, inp)
        #cv.ConvertImage(self.acc, inp)
        return inp

averager = Averager()

def test_averager():
    averager = Averager(4, 4)
    return test_generic(averager.filter)

def face_detect(b):
    """
    dir(b)
    ['__class__', '__cmp__', '__delattr__', '__delitem__', '__delslice__',
    '__dict__', '__doc__', '__format__', '__getattribute__', '__getitem__',
    '__getslice__', '__grefcount__', '__gstminiobject_init__', '__gtype__',
    '__hash__', '__init__', '__len__', '__new__', '__reduce__', '__reduce_ex__',
    '__repr__', '__setattr__', '__setitem__', '__setslice__', '__sizeof__',
    '__str__', '__subclasshook__', 'caps', 'copy', 'copy_on_write',
    'create_sub', 'data', 'duration', 'flag_is_set', 'flag_set', 'flag_unset',
    'flags', 'get_caps', 'is_metadata_writable', 'is_span_fast', 'join',
    'make_metadata_writable', 'merge', 'offset', 'offset_end', 'set_caps',
    'size', 'span', 'stamp', 'timestamp']
    """
    width = b.caps[0]['width']
    height = b.caps[0]['height']
    inp = cv.fromarray(numpy.fromstring(b.data, dtype=numpy.uint8).reshape(width, height, 3))
    out = averager.filter(inp)
    #cv.DrawContours(inp, )
    return gst.Buffer(numpy.fromstring(out.tostring(), dtype=numpy.uint8))

def null_cv_test(b):
    print dir(b)
    inp = cv.fromarray(numpy.fromstring(b.data, dtype=numpy.uint8).reshape(720,480,3))
    out = inp
    return gst.Buffer(numpy.fromstring(out.tostring(), dtype=numpy.uint8))

def cvtest(b):
    print "cvtest", len(b)
    return b

# trying out different colorspaces, and trying to use builtin gstreamer colorspace convertion (ffmpegcolorspace)
yuv_capabilities = 'video/x-raw-yuv,width=320,height=240,format=(fourcc)I420,framerate=(fraction)5/1'
#rgb_capabilities = 'video/x-raw-rgb,width=320,height=240,depth=24,framerate=(fraction)5/1'
rgb_capabilities = 'video/x-raw-rgb,width=640,height=480,depth=24'

class DetectProcess(Process):

    def __init__(self, inq, outq):
        Process.__init__(self)
        self.inq = inq
        self.outq = outq

    def run(self):
        print "detect: running"
        while True:
            inp = self.inq.get()
            assert(inp == 'test')
            self.outq.put('testout')
        print "detect: got from queue"
        self.video_tracker = VideoTracker(initial_frame=inp, on_cx_cy=self.on_cx_cy)
        print "detect: putting into queue"
        self.outq.put(inp)
        while True:
            inp = self.inq.get()
            ret = inp
            #ret = self.video_tracker.on_frame(inp)
            self.outq.put(ret)

class Controller(object):
    def __init__(self):
        self.video_tracker = None
        print "CONNECTING Motor"
        motor.connect()
        print "CONNECTING Trigger"
        self.trigger = trigger.Trigger()
        print "CONNECTING Joystick"
        self.init_joystick()
        self.manual = False
        self.x = None
        self.y = None
        self.fire_duration = 200
        self.video_tracker = None

    def _unused_init_detec_process(self):
        self.video_in = Queue()
        self.video_out = Queue()
        self.detect_process = DetectProcess(inq=self.video_in, outq=self.video_out)
        self.detect_process.start()

    def on_frame(self, b):
        ret = inp = numpy.fromstring(b.data, dtype=numpy.uint8).reshape(480,720,3)
        if not self.video_tracker:
            self.video_tracker = VideoTracker(initial_frame=inp, on_cx_cy=self.on_cx_cy)
        else:
            ret = self.video_tracker.on_frame(inp)
        return gst.Buffer(ret)

    def on_frame_process(self, b):
        ret = inp = numpy.fromstring(b.data, dtype=numpy.uint8).reshape(480,720,3)
        print "pushing"
        self.video_in.push('test')
        print "popping"
        ret_unused = self.video_out.pop()
        assert(ret_unused == 'testout')
        print "popped"
        return gst.Buffer(ret)

    def init_joystick(self):
        self.j = joystick.Joystick()
        self.j.connect('axis', self.on_axis)
        self.j.connect('button', self.on_button)

    def on_axis(self, signal, code, value):
        print "on_axis %s %s" % (code, value)
        #print "on_axis %d, %d" % (code, value)
        if code not in [0, 1, 2]:
            return
        if code == 0:
            self.x = value
            if self.manual:
                motor.theta.set(state.x - 127)
        elif code == 1:
            self.y = value
            if self.manual:
                motor.pitch.set(state.y - 127)
        else:
            fire_duration = 100 + (float(value) / 255.0) * 900
            print "joy: %d => fire dur %d" % (value, fire_duration)
            self.fire_duration = int(fire_duration)

    def on_button(self, signal, code, value):
        print "on_button: %d, %d" % (code, value)
        if value != 1 or code != 0:
            return
        print " **** FIRE ****"
        self.trigger.fire(self.fire_duration)

    def on_cx_cy(self, cx, cy):
        0/0
        print "controller: got (%d, %d)" % (cx, cy)
        cx -= 720 / 2
        cy -= 480 / 2
        for axis, val in [(motor.theta, cx), (motor.pitch, cy)]:
            if abs(val) > 10:
                print "action %r" % axis
                axis.set(200 if cx > 0 else -200)

class GTK_Main(object):

    def __init__(self, controller):
        self._window = window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title("iBalloon")
        window.set_default_size(500, 400)
        window.connect("destroy", gtk.main_quit, "WM destroy")
        vbox = gtk.VBox()
        window.add(vbox)
        self.movie_window = gtk.DrawingArea()
        vbox.add(self.movie_window)
        hbox = gtk.HBox()
        vbox.pack_start(hbox, False)
        hbox.set_border_width(10)
        hbox.pack_start(gtk.Label())
        self.buttons = []
        for label, clicked in [
                    ('quit', self.exit)
                ]:
            button = gtk.Button(label)
            button.connect('clicked', clicked)
            hbox.pack_start(button, False)
            self.buttons.append(button)
        self.button = self.buttons[0]
        hbox.add(gtk.Label())
        window.show_all()

        # Set up the gstreamer pipeline (v4l2src / dc1394src)
        if options.test:
            cmd = "multifilesrc location=video/recs/yoni/yuv/%05d loop=1 caps=video/x-raw-yuv,format=(fourcc)YUY2,width=(int)720,height=(int)480,framerate=(fraction)30000/1001,pixel-aspect-ratio=(fraction)40/33,interlaced=(boolean)true ! ffmpegcolorspace ! video/x-raw-rgb ! queue name=a . ffmpegcolorspace name=b ! video/x-raw-yuv ! xvimagesink"
        else:
            #cmd = "dv1394src ! dvdemux ! dvdec ! ffmpegcolorspace ! video/x-raw-rgb ! queue name=a . ffmpegcolorspace name=b ! video/x-raw-yuv ! videoflip method=clockwise ! xvimagesink"
            cmd = "dv1394src ! dvdemux ! dvdec ! queue ! ffmpegcolorspace ! queue ! video/x-raw-rgb ! queue name=a . ffmpegcolorspace name=b ! video/x-raw-yuv ! xvimagesink"
        #src = 'videotestsrc'
        #cmd = "%(src)s . ffmpegcolorspace name=b ! 'video/x-raw-yuv' ! xvimagesink" % {'src': src}
        print "using parse_launch on %r" % cmd
        self.player = gst.parse_launch(cmd)
        self.a = self.player.get_by_name('a')
        self.b = self.player.get_by_name('b')
        #gst.element_factory_make
        self.fun = FunElement()
        self.fun.setFun(controller.on_frame)
        self.player.add(self.fun)
        #self.player.add(self.fun, final)
        if options.noaction:
            print "not doing any unlinking / linking"
        else:
            #gst.element_unlink_many(self.a, self.b)
            gst.element_link_many(self.a, self.fun, self.b)

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("sync-message::element", self.on_sync_message)
        self.player.set_state(gst.STATE_PLAYING)

    def exit(self, widget, data=None):
        gtk.main_quit()

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            # Assign the viewport
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            imagesink.set_xwindow_id(self.movie_window.window.xid)

if __name__ == '__main__':
    """
    Tried adding sleep, not really helping, to avoid these:

initializing video tracker

(main.py:2569): Gdk-ERROR **: The program 'main.py' received an X Window System error.
This probably reflects a bug in the program.
The error was 'BadIDChoice (invalid resource ID chosen for this connection)'.
  (Details: serial 282 error_code 14 request_code 1 minor_code 0)
  (Note to programmers: normally, X errors are reported asynchronously;
   that is, you will receive the error a while after causing it.
   To debug your program, run it with the --sync command line
   option to change this behavior. You can then get a meaningful
   backtrace from your debugger if you break on the gdk_x_error() function.)
Trace/breakpoint trap (core dumped)

initializing video tracker
[xcb] Unknown sequence number while processing queue
[xcb] Most likely this is a multi-threaded client and XInitThreads has not been called
[xcb] Aborting, sorry about that.
python: xcb_io.c:273: poll_for_event: Assertion `!xcb_xlib_threads_sequence_lost' failed.

    """
    options = get_options()
    controller = Controller()
    GTK_Main(controller)
    gtk.main()
