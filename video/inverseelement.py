#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# sinkelement.py
# (c) 2005 Edward Hervey <edward@fluendo.com>
# Licensed under LGPL
#
# Small test application to show how to write a sink element
# in 20 lines in python
#
# Run this script with GST_DEBUG=python:5 to see the debug
# messages

import numpy

import pygst
pygst.require('0.10')
import gst
import gobject
gobject.threads_init ()

#
# Simple Sink element created entirely in python
#

VLOOPBACK_SINK = '/dev/video1'

class FunElement(gst.Element):
    #fmt = VIDEO_PALETTE_RGB24

    _sinkpadtemplate = gst.PadTemplate ("sinkpadtemplate",
                                        gst.PAD_SINK,
                                        gst.PAD_ALWAYS,
                                        gst.caps_new_any())

    _srcpadtemplate = gst.PadTemplate ("srcpadtemplate",
                                        gst.PAD_SRC, # PAD_SINK, PAD_SRC, PAD_UNKNOWN
                                        gst.PAD_ALWAYS,
                                        gst.caps_new_any())


    def __init__(self, fun=None):
        gst.Element.__init__(self)
        gst.info('creating sinkpad')
        self.fun = fun
        self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")
        gst.info('adding sinkpad to self')
        self.add_pad(self.sinkpad)
        self.srcpad = gst.Pad(self._srcpadtemplate, "src")
        gst.info('adding srcpad to self')
        self.add_pad(self.srcpad)

        gst.info('setting chain/event functions')
        self.sinkpad.set_chain_function(self.chainfunc)
        self.sinkpad.set_event_function(self.eventfunc)

    def setFun(self, fun):
        self.fun = fun

    def _calc_next(self):
        """Given the configured interval, calculate when the next
           frame should be added to the output"""
        d = self.interval
        self.next = d + int(time.time() / d)*d

    def chainfunc(self, pad, buffer):
        #self.info("%s timestamp(buffer):%d" % (pad, buffer.timestamp))
        #print len(buffer), repr(buffer.data[:10]), "..."
        if self.fun:
            b2 = self.fun(buffer)
            b2.timestamp = buffer.timestamp
            b2.flag_set(buffer.flags)
            b2.set_caps(buffer.get_caps())
            b2.duration = buffer.duration
            #print len(b2), repr(b2.data[:10]), "..."
        else:
            b2 = buffer
        #import pdb; pdb.set_trace()
        self.srcpad.push(b2)
        return gst.FLOW_OK

    def eventfunc(self, pad, event):
        print("%s event:%r" % (pad, event.type))
        self.info("%s event:%r" % (pad, event.type))
        self.srcpad.push_event(event)
        return True

def inverse(buffer):
    return gst.Buffer(255 - numpy.fromstring(buffer.data, dtype=numpy.uint8))

class InverseElement(FunElement):
    def __init__(self):
        FunElement.__init__(self, inverse)

gobject.type_register(InverseElement)
gobject.type_register(FunElement)

#
# Code to test the MySink class
#

def test():
    #src = 'v4l2src device=/dev/video0'
    #src = 'videotestsrc'
    src = "dv1394src ! dvdemux ! dvdec "

    #pipeline = gst.parse_launch("%(src)s name=src ! queue ! videorate ! video/x-raw-yuv,width=320,height=240,format=(fourcc)I420,framerate=(fraction)5/1 ! ffmpegcolorspace name=last ! queue ! smokeenc ! udpsink host=132.70.7.53 port=5799" % locals())
    #pipeline = gst.parse_launch("%(src)s name=src ! queue ! videorate ! video/x-raw-yuv,width=320,height=240,format=(fourcc)I420,framerate=(fraction)5/1 ! ffmpegcolorspace name=last" % locals())
    pipeline = gst.parse_launch("%(src)s name=src ! ffmpegcolorspace name=last" % locals())
    # ! filesink location=/tmp/test.raw name=last

    mainloop = gobject.MainLoop()

    def on_eos(bus, msg):
        print "on_eos", bus, msg
        mainloop.quit()

    def on_error(bus, msg):
        error = msg.parse_error()
        print "on_error", bus, error
        mainloop.quit()

    # Create bus and connect several handlers
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect('message::eos', on_eos)
    #bus.connect('message::tag', on_tag)
    bus.connect('message::error', on_error)

    #gst.info('About to create MySink')
    #sink = InverseElement()

    def onbuffer(*args, **kw):
        print args, kw
        return True
    src = pipeline.get_by_name('src')
    last = pipeline.get_by_name('last')
    sink = InverseElement()
    pipeline.add(sink)
    last.link(sink)
    #src.get_pad('src').add_buffer_probe(onbuffer)
    #sink.get_pad('sink').add_buffer_probe(onbuffer)

    pipeline.set_state(gst.STATE_PLAYING)

    mainloop.run()

if __name__ == '__main__':
    test()

