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
        self.on_serial_block = self._dummy_on_serial_block
        self._on_done_set_shot_length = []
        gobject.io_add_watch(self.s.fileno(), gobject.IO_IN, self._on_serial)
        # Handle responses from serial - instead of parsing the whole
        # thing just know that a timeout means serial has done with answering us
        self.buf = []
        self.count = 0

    def set_shot_length(self, shot_length, f=None):
        if f:
            self.on_done_set_shot_length(f)
        self.s.write('shotLength=%d\n' % shot_length)

    def _dummy_on_serial_block(self, data):
        print ">>> serial <<<"
        print "got %r" % data

    def _on_serial(self, fd, condition, user_data=None):
        data = self.s.read()
        self.buf.append(data)
        self.count += 1
        gobject.timeout_add(50, self.on_timeout, self.count)
        return True

    def on_timeout(self, count):
        if self.count != count:
            return False
        data = ''.join(self.buf)
        del self.buf[:]
        if 'ShotLength Set to' in data:
            self._on_done_set_shot_length_cb()
        self.on_serial_block(data)

    def fire(self, shot_length=200):
        if shot_length != self.shot_length:
            self.set_shot_length(shot_length,
                                 lambda: self.s.write('s\n'))
        else:
            self.s.write('s\n')

    def on_done_set_shot_length(self, f):
        self._on_done_set_shot_length.append(f)

    def _on_done_set_shot_length_cb(self):
        print "arduino done setting shot length"
        for f in self._on_done_set_shot_length:
            f()
        del self._on_done_set_shot_length[:]

    def green_on(self):
        self.s.write('gon\n')

    def green_off(self):
        self.s.write('goff\n')

class SerialTester(object):

    def __init__(self, trigger):
        self.trigger = trigger
        non_block_stdin()
        gobject.io_add_watch(sys.stdin, gobject.IO_IN, self.on_stdin)

    def on_stdin(self, fd, condition):
        print ">>> stdin <<<"
        self.trigger.s.write(fd.read())
        return True

class Tester(SerialTester):
    def __init__(self, tr):
        SerialTester.__init__(self, tr)

    def on_stdin(self, fd, condition):
        print ">>> tester <<<"
        cmd = fd.read().strip().split()
        print cmd
        if cmd[0] == 'fire':
            if len(cmd) == 2:
                self.trigger.fire(int(cmd[1]))
            else:
                self.trigger.fire()
        elif cmd == 'gon':
            self.trigger.green_on()
        elif cmd == 'goff':
            self.trigger.green_off()
        return True

def non_block_stdin():
    # make stdin a non-blocking file
    fd = sys.stdin.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

def main():
    tr = Trigger()
    #tester = SerialTester(tr)
    tester = Tester(tr)
    ml = gobject.MainLoop()
    ml.run()

if __name__ == '__main__':
    main()
