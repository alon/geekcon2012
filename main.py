#!/usr/bin/env python

"""
To run with firewire camera, you need to make sure the permissions are correct
on the device files.
"""

from __future__ import with_statement

debug = False
motor_debug = True

import optparse
import atexit
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
import joystick

def get_options():
    global debug
    global motor_debug
    parser = optparse.OptionParser()
    parser.add_option('-n', '--noaction', dest='noaction', help="don't actually do anything with the image - just show the camera picture", action='store_true')
    parser.add_option('-t', '--test', dest='test', help="use videotestsrc", action='store_true')
    parser.add_option('--debug', default=debug, action='store_true')
    parser.add_option('--motor-debug', default=motor_debug, action='store_true')
    opts, args = parser.parse_args()
    debug = opts.debug
    motor_debug = opts.motor_debug
    return opts

from video.inverseelement import FunElement

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

def get_motor(motor_debug):
    if motor_debug:
        motor = __import__('fake_motor')
    else:
        motor = __import('motor')
    return motor

def get_trigger(debug):
    if debug:
        trigger = __import__('fake_trigger')
    else:
        trigger = __import__('trigger')
    return trigger

class Controller(object):
    def __init__(self):
        motor = get_motor(motor_debug)
        trigger = get_trigger(debug)
        self.motor = motor
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

    def _unused_init_detect_process(self):
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
                self.motor.theta.set(state.x - 127)
        elif code == 1:
            self.y = value
            if self.manual:
                self.motor.pitch.set(state.y - 127)
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
        #print "controller: got (%d, %d)" % (cx, cy)
        cx -= 720 / 2
        cy -= 480 / 2
        for axis, val in [(self.motor.theta, cx), (self.motor.pitch, cy)]:
            if abs(val) > 10:
                print "action %r" % axis
                axis.set(200 if cx > 0 else -200)

def turn_off_motors(*args):
    motor = get_motor(motor_debug)
    motor.disable()

atexit.register(turn_off_motors)

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
            firewire = "dv1394src ! dvdemux ! dvdec"
            v4l2 = "v4l2src"
            cmd = v4l2 + " ! ffmpegcolorspace ! video/x-raw-rgb ! queue name=a . ffmpegcolorspace name=b ! video/x-raw-yuv ! xvimagesink"
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
            #print "ignoring window.xid %d" % self.movie_window.window.xid
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
