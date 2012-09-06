from pymodbus.client.sync import ModbusTcpClient as ModbusClient

PLS_HOST = '192.168.1.202'

# enables both motors
coil_enable = 0
coil_reset  = 3

class AxisData(object):
    def __init__(self, coil_execute,
            register_target,
            discrete_enabled
            input_status):
        self.coil_enable = coil_enable
        self.register_target = register_target
        self.discrete_enabled = discrete_enabled
        self.input_status = input_status

theta_data = AxisData(
            coil_execute=1,
            register_target=0,
            discrete_enabled=0,
            input_status=1,
        )

pitch_data = AxisData(
            coil_execute=2,
            register_target=1,
            discrete_enabled=1,
            input_status=3,
        )

def enable(client):
    client.write_coil(coil_enable, 1, 0)

def disable(client):
    client.write_coil(coil_enable, 0, 0)

class Axis(object):
    data = None

    def set(self, val):
        client.register(self.data.register_target, val, 0)

    def enabled(self):
        return client.read_discrete_inputs(0, 1, 0).bits[self.data.discrete_enabled]

    def pos(self):
        return client.read_input_registers(self.data.input_status, 1, 0).registers[0]

class Theta(Axis):
    data = theta_data

class Pitch(Axis):
    data = pitch_data

client = ModbusClient(PLS_HOST)
theta = Theta()
pitch = Pitch()
