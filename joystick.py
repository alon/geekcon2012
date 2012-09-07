#!/usr/bin/python
'''
Copyright 2009 Jezra Lickter

This software is distributed AS IS. Use at your own risk.
If it borks your system, you have  been forewarned.

This software is licensed under the LGPL Version 3
http://www.gnu.org/licenses/lgpl-3.0.txt


for documentation on Linux Joystick programming please see
http://www.mjmwired.net/kernel/Documentation/input/joystick-api.txt
'''

import gtk
from glob import glob
import gobject #needed for sending signals
import struct #needed for holding chunks of data

class Joystick(gobject.GObject):
    '''The Joystick class is a GObject that sends signals that represent
    Joystick events'''
    TYPE_BUTTON = 0x01 #button pressed/released
    TYPE_AXIS = 0x03  #axis moved
    TYPE_INIT = 0x80  #button/axis initialized
    #see http://docs.python.org/library/struct.html for the format determination
    EVENT_FORMAT = "QQHHi"
    EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

    # This is for the logitech attach 3 only!!
    FIRST_BUTTON = 288
    X_AXIS = 0
    X_POSITIVE = 'right'
    Y_AXIS = 1
    Y_POSITIVE = 'down'
    Z_AXIS = 2
    Z_POSITIVE = 'bottom (away)'

    # we need a few signals to send data to the main
    '''signals will return 4 variables as follows:
    1. a string representing if the signal is from an axis or a button
    2. an integer representation of a particular button/axis
    3. an integer representing axis direction or button press/release
    4. an integer representing the "init" of the button/axis
    '''
    __gsignals__ = {
    'axis' :
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
    (gobject.TYPE_INT,gobject.TYPE_INT,gobject.TYPE_INT)),
    'button' :
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
    (gobject.TYPE_INT,gobject.TYPE_INT,gobject.TYPE_INT))
    }

    def __init__(self, device):
        gobject.GObject.__init__(self)
        #define the device
        #error check that this can be read
        try:
            #open the joystick device
            self.device = open(device, 'r', 0)
            #keep an eye on the device, when there is data to read, execute the read function
            gobject.io_add_watch(self.device, gobject.IO_IN, self.read)
        except Exception,ex:
            #raise an exception
            raise Exception( ex )

    def read(self, arg0='', arg1=''):
        ''' read the button and axis press event from the joystick device
        and emit a signal containing the event data
        '''
        #read self.EVENT_SIZE bytes from the joystick
        print "blocking"
        read_event = self.device.read(self.EVENT_SIZE)
        if len(read_event) != self.EVENT_SIZE:
            print "got %d bytes (expected %d): %s" % (len(read_event), self.EVENT_SIZE.
                    repr(read_event))
            return True
        #get the event structure values from  the read event
        seconds, nanos, type, code, value = struct.unpack(self.EVENT_FORMAT, read_event)
        print "%10d %10d %d %d %d" % (seconds, nanos, type, code, value)
        #get just the button/axis press event from the event type
        #event = type & ~self.EVENT_INIT
        #get just the INIT event from the event type
        #init = type & ~event
        init = 0
        if type == self.TYPE_AXIS:
            signal = "axis"
        elif type == self.TYPE_BUTTON:
            signal = "button"
            code = code - self.FIRST_BUTTON
        else:
            print "ignored type = %r" % type
            return True
            #import pdb; pdb.set_trace()
            #raise SystemExit
        if signal:
            print("%s %s %s %s" % (signal,code,value,init) )
            self.emit(signal,code,value,init)

        return True

def find_joystick(name='Logitech'):
    for path in glob('/sys/class/input/*/name'):
        #print "checking %s" % path
        with open(path) as fd:
            dev_name = fd.read().strip()
            if name in dev_name:
                print "Found %s" % path
                event = glob(path.rsplit('/', 1)[0] + '/event*')[0]
                return '/dev/input/%s' % event.rsplit('/', 1)[1]
    print "Found none"
    return None

class GUI(object):
    def __init__(self, j):
        self.j = j
        self.window = window = gtk.Window()
        self.status = gtk.Label()
        self.status.set_text('       ')
        self.window.add(self.status)
        self.window.show_all()
        self.j.connect('axis', self.on_event)
        self.j.connect('button', self.on_event)

    def on_event(self, *args):
        print "got ", repr(args)
        self.status.set_text(repr(args))


if __name__ == "__main__":
    devname = find_joystick()
    if devname is None:
        print "You don't have any joystick named 'Logitech'"
        raise SystemExit
    print "Opening %s" % devname
    #with open(devname) as fd:
    #    while True:
    #        fd.read(100)
    try:
        j = Joystick(devname)
        gui = GUI(j)
        loop = gobject.MainLoop()
        loop.run()
    except Exception,e:
        print(e)
