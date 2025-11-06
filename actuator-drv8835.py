from gpiozero import PhaseEnableMotor
from gpiozero.pins.pigpio import PiGPIOFactory

MAX_SPEED = 480
factory = PiGPIOFactory()

steer_motor = PhaseEnableMotor(5, 12, pin_factory=factory)
drive_motor = PhaseEnableMotor(6, 13, pin_factory=factory)

# init
def init(default_speed=50):
    steer_motor.stop()
    drive_motor.stop()

    set_speed(default_speed)

# throttle
cur_speed = 1
move_state = 0

def get_max_speed():
    return 1

def set_speed(speed):
    global cur_speed
    global move_state
    speed = max(-1, min(1, speed))
    cur_speed = speed
    if move_state == -1:
        rew()
    elif move_state == 1:
        ffw()

def get_speed():
    return int(cur_speed * 100)

def stop():
    global move_state
    drive_motor.stop()
    move_state=0
        
def ffw():
    global move_state
    drive_motor.forward(abs(cur_speed))
    move_state=1

def rew():
    global move_state
    drive_motor.backward(abs(cur_speed))
    move_state=-1

# steering
def center():
    steer_motor.stop()

def left(speed=-1):
    steer_motor.backward(abs((int(speed))))

def right(speed=1):
    steer_motor.forward(abs(int(speed)))

# exit    
def turn_off():
    stop()
    center()
