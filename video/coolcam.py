#!/usr/bin/env python

"""
To run with firewire camera, you need to make sure the permissions are correct
on the device files.
"""

from __future__ import with_statement

import datetime

import ctypes
import numpy

import cv

import sys, os
import pygtk, gtk, gobject
import pygst
pygst.require("0.10")

# Do it early to avoid xcb assertions
gtk.gdk.threads_init()

# don't let gst handle the --help for us
import sys
sargs = set(sys.argv)

def get_options():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-n', '--noaction', dest='noaction', help="don't actually do anything with the image - just show the camera picture", action='store_true')
    parser.add_option('-t', '--test', dest='test', help="use videotestsrc", action='store_true')
    opts, args = parser.parse_args()
    return opts

import gst

from inverseelement import InverseElement, FunElement, inverse

#<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# Look for impr dll
import os
lib = os.popen('uname -m').read().strip() == 'x86_64' and './libimpr.64.so' or './libimpr.32.so'
try:
    # get it at http://cba.si/impr/
    # to compile 64 bit version, remember to add -fPIC to EXTRA in the Makefile
    impr = ctypes.CDLL(lib)
except:
    print "missing %s" % lib
    class Empty(object):
        def __getattr__(self, x):
            return self.passthrough

        def passthrough(self, x):
            return x
    impr = Empty()
#<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

def manhatten_8bit(pixels):
    # hopefully, this doesn't blow up.
    #impr.impr_manhattan_distance(b.data, b.data, 200, 200)
    #segmentize_8
    s = (pixels>>4).astype(numpy.uint8).tostring()
    impr.impr_manhattan_distance(s, s, 100, 100)
    return numpy.fromstring(s, dtype=numpy.uint8)

max_12 = (1<<12) - 1

def generate_smooth(b):
    a = numpy.arange(len(b), dtype=numpy.int8)
    return gst.Buffer(a.tostring())

def do_8bit_fun(b, f=None):
    # gotchas: if you have a uint8 array and you shift left, it
    # respects it's data type, and <<8 becomes 0 - so I cast to
    # uint16 at first.
    base8 = numpy.fromstring(b.data, dtype=numpy.uint8)
    base = base8.astype(numpy.uint16)
    pixels = numpy.zeros(len(b)*2/3, dtype=numpy.uint16)
    pixels[0::2] = base[0::3] + ((base[1::3]&0xf)<<8)
    pixels[1::2] = (base[1::3]>>4) + (base[2::3]<<4)
    # do something, we are going to try inverse
    if f:
        pixels = f(pixels)
    # now pack back to 12 bits
    #import pdb; pdb.set_trace()
    p_out = numpy.zeros(len(b), dtype=numpy.uint8)
    p_out[0::3] = pixels[0::2]&0xff
    p_out[1::3] = ((pixels[0::2]&0xf00)>>8) + ((pixels[1::2]&0xf)<<4)
    p_out[2::3] = (pixels[1::2]&0xff0)>>4
    #import pdb; pdb.set_trace()
    return gst.Buffer(p_out.tostring())

def manhatten(b):
    return do_8bit_fun(b, manhatten_8bit)

def magic(b):
    return do_8bit_fun(b, lambda pixels: (pixels.astype(float)*0.8).astype(numpy.uint8))

def record(b):
    with open(datetime.datetime.now().strftime('%Y%m%d_%H%M%S'),'w+') as fd:
        fd.write(b)
    return b

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
    return gst.Buffer(numpy.fromstring(out.tostring(), dtype=numpy.uint8))

def null_cv_test(b):
    print dir(b)
    inp = cv.fromarray(numpy.fromstring(b.data, dtype=numpy.uint8).reshape(720,480,3))
    out = inp
    return gst.Buffer(numpy.fromstring(out.tostring(), dtype=numpy.uint8))

def cvtest(b):
    print "cvtest", len(b)
    return b

fun_functions = [face_detect, inverse, magic, manhatten, record]

# trying out different colorspaces, and trying to use builtin gstreamer colorspace convertion (ffmpegcolorspace)
yuv_capabilities = 'video/x-raw-yuv,width=320,height=240,format=(fourcc)I420,framerate=(fraction)5/1'
#rgb_capabilities = 'video/x-raw-rgb,width=320,height=240,depth=24,framerate=(fraction)5/1'
rgb_capabilities = 'video/x-raw-rgb,width=640,height=480,depth=24'

class GTK_Main(object):

    def __init__(self):
        self.fun_functions = fun_functions
        self._window = window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title("Webcam-Viewer")
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
            ('debug', self.toggle_debug)] + [
                (f.func_name, lambda w, self=self, f=f: self.set_fun(f))
                    for f in self.fun_functions] + [('quit', self.exit)]:
            button = gtk.Button(label)
            button.connect('clicked', clicked)
            hbox.pack_start(button, False)
            self.buttons.append(button)
        self.button = self.buttons[0]
        hbox.add(gtk.Label())
        window.show_all()

        # Set up the gstreamer pipeline
        # v4l2src
        # dc1394src
        if options.test:
            #src = 'videotestsrc ! %s ! ffmpegcolorspace ! videorate' % rgb_capabilities
            cmd = "multifilesrc location=recs/black/%05d loop=1 caps=video/x-raw-yuv,format=(fourcc)YUY2,width=(int)720,height=(int)480,framerate=(fraction)30000/1001,pixel-aspect-ratio=(fraction)40/33,interlaced=(boolean)true ! ffmpegcolorspace ! video/x-raw-rgb ! queue name=a . ffmpegcolorspace name=b ! video/x-raw-yuv ! xvimagesink"
        else:
            #src = 'v4l2src ! %s ! ffmpegcolorspace ! videorate' % rgb_capabilities
            #src = 'v4l2src ! videorate'
            #src = 'dc1394src'
            #src = "dv1394src ! dvdemux ! dvdec ! queue ! ffmpegcolorspace"
            #src = "dv1394src ! dvdemux ! dvdec ! ffmpegcolorspace ! video/x-raw-rgb,width=720,height=480"
            #src = "dv1394src ! dvdemux ! dvdec ! ffmpegcolorspace ! 'video/x-raw-rgb' ! queue name=a"
            cmd = "dv1394src ! dvdemux ! dvdec ! ffmpegcolorspace ! video/x-raw-rgb ! queue name=a . ffmpegcolorspace name=b ! video/x-raw-yuv ! xvimagesink"
        #src = 'videotestsrc'
        #cmd = "%(src)s . ffmpegcolorspace name=b ! 'video/x-raw-yuv' ! xvimagesink" % {'src': src}
        print "using parse_launch on %r" % cmd
        self.player = gst.parse_launch(cmd)
        self.a = self.player.get_by_name('a')
        self.b = self.player.get_by_name('b')
        #gst.element_factory_make
        self.fun = FunElement()
        self.fun.setFun(self.fun_functions[0])
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
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)
        self.player.set_state(gst.STATE_PLAYING)

    def set_fun(self, f):
        self.fun.setFun(f)

    def toggle_debug(self, w):
        self._debug = True

    def exit(self, widget, data=None):
        gtk.main_quit()

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
            self.button.set_label("Start")
        elif t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.player.set_state(gst.STATE_NULL)
            self.button.set_label("Start")

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
    options = get_options()
    GTK_Main()
    gtk.main()
