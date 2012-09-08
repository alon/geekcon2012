#!/usr/bin/python
import sys
import os
import fcntl

import gobject
import serial

class Trigger(object):

    def __init__(self, devname='/dev/ttyACM0'):
        self.s = serial.Serial(devname)
        self.s.nonblocking()
        self.shot_length = 200
        self.on_serial = self._dummy_on_serial
        gobject.io_add_watch(self.s.fileno(), gobject.IO_IN, self._on_serial)

    def set_shot_length(self, shot_length):
        slef.s.write('shotLength=%d\n' % shot_length)

    def _dummy_on_serial(self, data):
        print "got %r" % data

    def _on_serial(self, fd, condition, user_data=None):
        data = self.s.read()
        self.on_serial(data)
        return True

    def fire(self, shot_length=200):
        if shot_length != self.shot_length:
            self.set_shot_length(shot_length)

class Tester(object):
    def __init__(self, trigger):
        self.buf = []
        self.count = 0
        self.trigger = trigger
        self.trigger.on_serial = self.on_serial # TODO: gobject signals..
        non_block_stdin()
        gobject.io_add_watch(sys.stdin, gobject.IO_IN, self.on_stdin)

    def on_serial(self, data):
        self.buf.append(data)
        self.count += 1
        gobject.timeout_add(50, self.on_timeout, self.count)

    def on_timeout(self, count):
        if self.count != count:
            return False
        print ''.join(self.buf)
        del self.buf[:]

    def on_stdin(self, fd, condition):
        print ">>> stdin <<<"
        self.trigger.s.write(fd.read())
        return True

def non_block_stdin():
    # make stdin a non-blocking file
    fd = sys.stdin.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

def main():
    tr = Trigger()
    tester = Tester(tr)
    ml = gobject.MainLoop()
    ml.run()

if __name__ == '__main__':
    main()
