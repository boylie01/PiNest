#!/usr/bin/python
import time
from datetime import datetime
import RPi.GPIO as GPIO
import subprocess
import os
import httplib2
import thread

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

#####################################################
# Turn Debugging off or on
debug = False
global log_debug
log_debug = True
global date
date = 0
global testing
testing = False
if testing:
    testing = 60
else:
    testing = 1

def log(message):
    global date
    file_name = '/home/pinest/Documents/PiNest/log.txt'
    time_stamp = datetime.now().time()
    if log_debug and not debug:
        if datetime.today().day > date:
            file_write = open(file_name, 'w')
            file_write.write((str(time_stamp)+' : '+message))
            file_write.close()
            date = datetime.today().day
        else:
            file_write = open(file_name, 'a')
            file_write.write(('\n'+ str(time_stamp)+' : '+message+' '))
            file_write.close()
            date = datetime.today().day
    if debug and not log_debug:
        print message


######################################################
# Set GPIO pin labelling mode
GPIO.setmode(GPIO.BCM)

# Input GPIOs
ch_switch = 27
inputs = [ch_switch]


# Output GPIOs
ch_relay = 17
ch_led = 22
relay = [ch_relay]  # ,psu_relay]
led = [ch_led]

# Globals
press_time = {}
ch_override = False
global schedule
schedule = {}


# Set up inputs & outputs
GPIO.setwarnings(False)
for each in inputs:
    log('pin '+str(each)+' - input')
    GPIO.setup(each, GPIO.IN)
for item in [relay, led]:
    for each in item:
        log('pin '+str(each)+' - output')
        GPIO.setup(each, GPIO.OUT, initial=False)


##############################################################
##############################################################
##############################################################
def set_gpio_state(gpio, state):
    if gpio not in relay and gpio not in led:
        return False
    else:
        if gpio in relay:
            GPIO.output(gpio, state)
            log('set relay to '+str(state))
        else:
            GPIO.output(gpio, not state)
            log('set relay to '+str(not state))
        return True


###############################################################
def initial_test():
    for thing in relay:
        if thing == ch_relay:
            set_gpio_state(thing, True)
            time.sleep(1)
            set_gpio_state(thing, False)
            time.sleep(0.25)
    for each_led in led:
        if each_led == ch_led:
            set_gpio_state(each_led, False)
            time.sleep(1)
            set_gpio_state(each_led, True)
            time.sleep(0.5)
    global initial_test_state
    initial_test_state = 'Initial test pass'


##############################################################

def get_gpio_state(gpio):
    if gpio not in relay and gpio not in led:
        return False
    else:
        log('gpio state - '+ str(GPIO.input(gpio)))
        return GPIO.input(gpio)


##############################################################

def ch_state(state):
    if state:
        log('CH ON')
        return True
    elif not state:
        return False


#############################################################
def button_press(channel):
    press_time[channel] = time.time()
    a = 0
    while not GPIO.input(channel) and a < 150:
        time.sleep(0.04)
        a += 1
    hold_time = time.time() - press_time[channel]
    log('Button Press! Hold time = ' + str(hold_time))
    if hold_time > 1.5:
        return True, hold_time
    else:
        return False, -1
        ###########################################################


def error_flash(type_flash):
    log('error flash')
    global log_debug
    log_debug = False
    set_gpio_state(22, True)
    for x in range(10):
        set_gpio_state(22, False)
        time.sleep(type_flash)
        set_gpio_state(22, True)
        log_debug = True


###############################################################
def current_temp(location):
    if location == 'living_room':
        folder_name = '/home/pinest/Documents/livingroom/Current_Temp'
        if not os.path.exists(folder_name):
            subprocess.call(['sudo fusermount -u '
                            '/home/pinest/Documents/livingroom'], shell=True)
            log('unmounted')

            subprocess.call([
                'sudo sshfs -o uid=1004 -o gid=1003 -o  '
                'idmap=user -o default_permissions -o '
                'allow_other pinest@192.168.1.91:/mnt/PiDrive/pinest'
                ' /home/pinest/Documents/livingroom'],shell=True)
            log('mounted')
        filename = (
            '/home/pinest/Documents/livingroom/Current_Temp/livingroom_temp.csv')
        f = open(filename)
        current_t = f.read().split(',')
        f.close()
        log('Current temperature in the living room is ' + str(current_t[1]))
        return float(current_t[1])
    elif location == 'utility':
        filename = '/home/pinest/Documents/Current_Temp/utility_temp.csv'
        f = open(filename)
        current_t = f.read().split(',')
        f.close()
        log('Current temperature in the utility is ' + str(current_t[1]))
        return float(current_t[1])


#############################################################

def timer(set_time):
    global key
    using_timer = True
    now = datetime.utcnow()
    if get_schedule():
        log('Loaded schedule online')
        schedule_start = schedule[0][0][0]
        if now == schedule_start or now > schedule_start:
            using_timer = False
            log('Event currently scheduled')
            set_time = True
            time_left = int(schedule[0][0][2] - (
                now - schedule_start).total_seconds() / 60)
            start_time = schedule[0][0][0]
            log('time left set by schedule = '+str(time_left))
            key = 0
        else:
            log('Using timer')
            time_left = set_time
            log('time left set by timer = ' + str(time_left))
            using_timer = True
            key = 'no key'
    else:
        log('Used offline schedule')
        for i in range(len(schedule.keys()) - 1):
            if schedule[i][0][0] <= now < schedule[(i + 1)][0][0] and now < schedule[i][0][3]:
                key = i
                schedule_start = schedule[key][0][0]
                Using_timer = False
                time_left = int(schedule[key][0][2] - (now - schedule_start).total_seconds() / 60)
                set_time = True
                log('Event set to start at ' + str(schedule_start))
                break
        else:
            log('Setting to last event and checking if the timer should run')
            try:
                key = (len(schedule.keys()) - 1)
                schedule_start = schedule[key][0][0]
                schedule_end = schedule[key][0][3]
                if now == schedule_start or schedule_start < now < schedule_end:
                    using_timer = False
                    time_left = int(schedule[key][0][2] - (now - schedule_start).total_seconds() / 60)
                    set_time = True
                    log('Offline event currently scheduled - time left: ' + str(time_left) + ' minutes')
            except KeyError:
                log('No events scheduled, using timer')
                time_left = set_time
                using_timer = True
                key = 'no key'
    if not set_time:
        log('only checked schedule, didnt run timer')
        key = 'no key'
        return True
    while time_left > 0:
        if not get_gpio_state(ch_relay):
            set_gpio_state(ch_relay, True)
            set_gpio_state(ch_led, False)
        log('running timer')
        log(str(time_left))
        current_temp_living_room = current_temp('living_room')
        log('current temp = ' + str(current_temp_living_room))
        if current_temp_living_room >= 23.0:
            log('temperature reached 23')
            return False
        elif not using_timer:
            if not get_gpio_state(ch_relay):
                log('turning on relay')
                set_gpio_state(ch_relay, True)
                log('turning on led')
                set_gpio_state(ch_led, False)
            if current_temp_living_room >= (schedule[key][0][1] + 0.0):
                log('current temperature over set temperature')
                while current_temp('living_room') >= ((schedule[key][0][1]) - 2.0):
                    log('Turning heating off until temperature drops 3 degrees')
                    if get_gpio_state(ch_relay):
                        set_gpio_state(ch_relay, False)
                        set_gpio_state(ch_led, True)
                    time.sleep(60)
                    time_left -= 1
        global testing
        time.sleep(60/testing)
        time_left -= 1
    return False


###############################################################

#def schedule_timer(time_start,time_left):


###############################################################

try:
    import argparse

    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    log('import error google')
    flags = None
log('setting flags for google')
SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'PiNest'


def get_credentials():
    log('get_credentials')
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(
            credential_dir, 'calendar-python-quickstart.json')
    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else:  # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
    return credentials


###############################################################

call = datetime.strptime('2015-02-01','%Y-%m-%d')
last_call = 0


def get_schedule():
    global call
    global testing
    global last_call
    if last_call == 0:
        last_call = datetime.strptime('2015-01-01','%Y-%m-%d')
    if ((call - last_call).total_seconds() / 1.0) > 300:
        last_call = call
        credentials = get_credentials()
        http = credentials.authorize(httplib2.Http())
        service = discovery.build('calendar', 'v3', http=http)
        now = datetime.utcnow()
        nowUTC = datetime.utcnow().isoformat()[:19] + 'Z' # 'Z' indicates UTC time
        dateTimeEnd = now.replace(hour=23,minute=59,second=59)
        end = dateTimeEnd.isoformat()[:19]+'Z'
        eventsResult = service.events().list(
            calendarId='primary', timeMin=nowUTC, timeMax=end,
            orderBy='startTime', singleEvents=True).execute()
        events = eventsResult.get('items', [])
        if not events:
            log('No upcoming events found.')
            call = datetime.now()
            return False
        global schedule
        i=0
        for event in events:
            start = datetime.strptime((str(event['start'].get('dateTime'))), '%Y-%m-%dT%H:%M:%SZ')
            calander_temp = int(event['summary'])
            stop = datetime.strptime((str(event['end'].get('dateTime'))), '%Y-%m-%dT%H:%M:%SZ')
            timedelta = (stop - start).total_seconds()/60
            schedule.setdefault(i,[])
            schedule[i].append([start, calander_temp,timedelta,stop])
            i +=1
            log('loaded schedule - ' + str(schedule))
            call = datetime.now()
        return True
    else:
        return False


#############################################################
detect = False
end_loop =0
initial_test_state = 0


def main():
    global detect
    global end_loop
    global initial_test_state
    if not detect:
        GPIO.add_event_detect(ch_switch, GPIO.FALLING, callback = button_activated, bouncetime=1000)  # add rising edge detection on channel
        detect = True
    try:
        if initial_test_state == 0:
            initial_test()
        now = datetime.utcnow()
        while True:
            start_loop = time.time()
            log('loop start '+ str(datetime.now().time()))
            while not GPIO.event_detected(ch_switch):
                if end_loop != 0:
                    if end_loop - start_loop < 30:
                        log('loop ended at no button press or schedule: ' + str(datetime.now().time()))
                        time.sleep(600/testing)
                        start_loop = time.time()
                log('Checking schedule and turning heating on if needed')
                timer(False)
                end_loop = time.time()
                if key != 'no key':
                    schedule_end = schedule[key][0][3]
                    if now < schedule_end:
                        while True:
                            log('Turning CH ON as scheduled' + str(schedule[key][0]))
                            if not timer(60):
                                end_loop = time.time()
                                log('CH Turned OFF')
                                break

    except KeyboardInterrupt:
        log('Stopped by user')
    finally:
        log('Cleaning up')
        GPIO.cleanup()

def button_activated(ch_switch):
    timer(False)
    if key == 'no key':
        if GPIO.event_detected(ch_switch):
                    log('Checking if button pressed')
                    real_press, time_pressed = button_press(ch_switch)
                    if real_press and 1.5 < time_pressed < 20:
                        state = ch_state(get_gpio_state(ch_relay))
                        if state:
                            log('CH already ON')
                            while True:
                                if not timer(60):
                                    set_gpio_state(ch_relay, False)
                                    set_gpio_state(ch_led, True)
                                    break
                        elif not state:
                            log('Turning ON for 1 hour')
                            set_gpio_state(ch_relay, True)
                            set_gpio_state(ch_led, False)
                            log('CH Turned ON')
                            while True:
                                if not timer(60):
                                    set_gpio_state(ch_relay, False)
                                    set_gpio_state(ch_led, True)
                                    log('CH Turned OFF')
                                    break
                        else:
                            log('error flash 1')
                            error_flash(1)

                    else:
                        log('error flash 0.5')
                        error_flash(0.5)
                        main()
    else:
        main()


if __name__ == "__main__":
    main()