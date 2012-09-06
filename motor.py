from pymodbus.client.sync import ModbusTcpClient as ModbusClient

"""
Theory of operation for each axis:

    Set wanted position
    Set execute bit
    Clear execute bit
    while the execute bit is set, the
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
            coil_home):
        """
        Target is relative
        Status is absolute
         - can check against limits
        """
        self.coil_enable = coil_enable
        self.register_target = register_target
        self.discrete_enabled = discrete_enabled
        self.input_status = input_status
        self.discrete_done = discrete_done
        self.coil_home = coil_home

theta_data = AxisData(
            coil_execute=1,
            register_target=0,
            discrete_enabled=0,
            input_status=1,
            discrete_done=2,
            coil_home=4,
        )

pitch_data = AxisData(
            coil_execute=2,
            register_target=1,
            discrete_enabled=1,
            input_status=3,
            discrete_done=3,
            coil_home=5,
        )

def enable(client):
    client.write_coil(coil_enable, 1, 0)

def disable(client):
    client.write_coil(coil_enable, 0, 0)

class Axis(object):
    data = None

    def set(self, val):
        """
        This implements a set that ignores done.
         set execute
         clear execute
        """
        client.write_register(self.data.register_target, val, 0)
        client.write_coil(self.data.coil_enable, 1, 0)
        # XXX sleep required???
        client.write_coil(self.data.coil_enable, 0, 0)

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

client = ModbusClient(PLS_HOST)
theta = Theta()
pitch = Pitch()
