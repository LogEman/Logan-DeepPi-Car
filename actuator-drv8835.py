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
cur_speed = MAX_SPEED
move_state = 0

def get_max_speed():
    return MAX_SPEED

def set_speed(speed):
    global cur_speed
    global move_state
    speed = int(MAX_SPEED * speed / 100)
    cur_speed = min(MAX_SPEED, speed)
    if move_state == -1:
        rew()
    elif move_state == 1:
        ffw()

def get_speed():
    return int(cur_speed * 100 / MAX_SPEED)

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
    steer_motor.backward(abs((int(speed*MAX_SPEED))))

def right(speed=1):
    steer_motor.forward(abs(int(speed*MAX_SPEED)))

# exit    
def turn_off():
    stop()
    center()
