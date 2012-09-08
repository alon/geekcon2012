#!/usr/bin/python

debug = True

if debug:
    print "DEBUG " * 10

import time

import gobject
from gobject import timeout_add

class FakeClient(object):
    def __init__(self, host):
        pass
    def connect(self):
        pass
    def write_register(self, *args):
        print repr(args)
    def write_coil(self, *args):
        print repr(args)

if debug:
    ModbusClient = FakeClient
else:
    from pymodbus.client.sync import ModbusTcpClient as ModbusClient

"""
Theory of operation for each axis:

    Set wanted position
    Set execute bit
    Clear execute bit
    while the execute bit is set, the

Theta CCW
"""

PLS_HOST = '192.168.1.202'

# enables both motors
coil_enable = 0
coil_reset  = 3

class AxisData(object):
    def __init__(self, coil_execute,
            register_target,
            discrete_enabled,
            input_status,
            discrete_done,
            coil_home,
            coil_jog_positive,
            coil_jog_negative,
            speed_target):
        """
        Target is relative
        Status is absolute
         - can check against limits
        """
        self.coil_enable = coil_enable
        self.coil_execute = coil_execute
        self.register_target = register_target
        self.discrete_enabled = discrete_enabled
        self.input_status = input_status
        self.discrete_done = discrete_done
        self.coil_home = coil_home
        self.coil_jog_positive = coil_jog_positive
        self.coil_jog_negative = coil_jog_negative
        self.speed_target = speed_target

theta_data = AxisData(
            coil_execute=1,
            register_target=0,
            discrete_enabled=0,
            input_status=0,
            discrete_done=2,
            coil_home=4,
            coil_jog_positive=6,
            coil_jog_negative=7,
            speed_target=2,
        )

pitch_data = AxisData(
            coil_execute=2,
            register_target=1,
            discrete_enabled=1,
            input_status=1,
            discrete_done=3,
            coil_home=5,
            coil_jog_positive=8,
            coil_jog_negative=9,
            speed_target=3,
        )

def reset():
    client.write_coil(coil_reset, 1, 0)
    client.write_coil(coil_reset, 0, 0)

def enable():
    client.write_coil(coil_enable, 1, 0)

def disable(client):
    client.write_coil(coil_enable, 0, 0)

def disabled(f):
    def wrapper(self, *args, **kw):
        if self._disabled:
            return
        return f(self, *args, **kw)
    wrapper.__doc__ = f.__doc__
    wrapper.__name__ = f.__name__
    return wrapper

class Axis(object):
    data = None

    def __init__(self, name, verbose=False):
        self.during = False
        self._execute = False
        self.name = name
        self._disabled = False
        self._verbose = verbose
        print "speed mode: enable execute"

    def disable(self):
        self._disabled = True

    def prnt(self, fmt, *args):
        if self._verbose:
            print("%s: %s" % (self.name, fmt % args))

    @disabled
    def set_position(self, val):
        """
        This implements a set that ignores done.
         set execute
         clear execute
        """
        if self.during:
            self.prnt( "ignoring execute, during previous one")
            return
        if val < 0:
            val = 65536 + val
        self.prnt( "writing %d -> %d" % (self.data.register_target, val))
        client.write_register(self.data.register_target, val, 0)
        self.during = True
        timeout_add(10, self.set_execute_set)

    def _set_execute(self, val):
        needed = not self.dead(val)
        if needed == self._execute:
            return
        self.prnt( "setting execute to %d" % int(needed))
        client.write_coil(self.data.coil_execute, 1, int(needed))
        self._execute = needed
        if not needed:
            client.write_coil(self.data.coil_jog_positive, 0)
            client.write_coil(self.data.coil_jog_negative, 0)

    def dead(self, val):
        return abs(val) < 10

    @disabled
    def set(self, val):
        """ set speed"""
        self._set_execute(val)
        if self.dead(val):
            return
        self.prnt( "setting jog+ %d jog- %d speed %d (%d,%d,%d)" % (int(val > 0),
                int(val < 0), abs(val),
                self.data.coil_jog_positive,
                self.data.coil_jog_negative,
                self.data.speed_target))
        client.write_coil(self.data.coil_jog_positive, int(val > 0))
        client.write_coil(self.data.coil_jog_negative, int(val < 0))
        client.write_register(self.data.speed_target, abs(val), 0)

    ######## Position logic Start
    def set_execute_set(self, *args):
        self.prnt( "setting coil %d" % self.data.coil_execute)
        client.write_coil(self.data.coil_execute, 1, 0)
        timeout_add(200, self.set_execute_clear)

    def set_execute_clear(self, *args):
        self.prnt( "clearing coil %d" % self.data.coil_execute)
        client.write_coil(self.data.coil_execute, 0, 0)
        self.during = False
    ######## Position logic End

    def home(self):
        client.write_coil(self.data.coil_home, 1, 0)
        client.write_coil(self.data.coil_home, 0, 0)

    def enabled(self):
        return client.read_discrete_inputs(0, 1, 0).bits[self.data.discrete_enabled]

    def pos(self):
        return client.read_input_registers(self.data.input_status, 1, 0).registers[0]

    def done(self):
        """ This returns 0 always if execute is down"""
        return client.read_discrete_inputs(0, 1, 0).bits[self.data.discrete_done]

class Theta(Axis):
    data = theta_data

class Pitch(Axis):
    data = pitch_data

connected = False
def connect():
    global connected
    if connected:
        return
    client.connect()
    connected = True
    reset()
    enable()

client = ModbusClient(PLS_HOST)
theta = Theta('theta')
pitch = Pitch('pitch')
#theta.disable()

def main():
    print "CONNECTING Modbus"
    connect()
    print "CONNECTING Trigger"
    if debug:
        trigger = FakeTrigger()
    else:
        trigger = __import__('trigger').Trigger()
    print "CONNECTING Joystick"
    joystick = __import__('joystick')
    j = joystick.Joystick()
    class state:
        x = None
        y = None
        fire_duration = 200

    def on_button(signal, code, value):
        print "on_button: %d, %d" % (code, value)
        if value != 1 or code != 0:
            return
        print " **** FIRE ****"
        trigger.fire(state.fire_duration)

    def on_button_do_execute(signal, code, value):
        if value != 1:
            return
        if code not in [0, 1]:
            print "ignored button, only 0 & 1 active"
            return
        if code == 0:
            if state.x is not None:
                print "execute theta"
                theta.set(state.x - 127)
            else:
                print "ignore theta, no axis motion yet"
        else:
            if state.y is not None:
                print "execute pitch"
                pitch.set(state.y - 127)
            else:
                print "ignore pitch, no axis motion yet"

    def on_axis(signal, code, value):
        #print "on_axis %d, %d" % (code, value)
        if code not in [0, 1, 2]:
            return
        if code == 0:
            state.x = value
            theta.set(state.x - 127)
        elif code == 1:
            state.y = value
            pitch.set(state.y - 127)
        else:
            fire_duration = 100 + (float(value) / 255.0) * 900
            print "joy: %d => fire dur %d" % (value, fire_duration)
            state.fire_duration = int(fire_duration)

    j.connect('axis', on_axis)
    j.connect('button', on_button)
    ml = gobject.MainLoop()
    ml.run()

if __name__ == '__main__':
    main()
