import time
from datetime import datetime
import RPi.GPIO as GPIO
import subprocess
import os
import httplib2

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

#####################################################
# Turn Debugging off or on
debug = False
log_debug = True
date = 0



def log(message):
    global date
    file_name = '/home/pinest/Documents/PiNest/log.txt'
    time_stamp = datetime.now().time()
    if log_debug and not debug:
        if datetime.today().day > date:
            with open(file_name, 'w') as file_write:
                file_write.write((str(time_stamp) + ' : ' + message))
            date = datetime.today().day
        else:
            with open(file_name, 'a') as file_write:
                file_write.write(('\n' + str(time_stamp) + ' : ' + message + ' '))
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

# Set up inputs & outputs
GPIO.setwarnings(False)
for each in inputs:
    log('pin ' + str(each) + ' - input')
    GPIO.setup(each, GPIO.IN)
for each in [ch_relay, ch_led]:
    log('pin ' + str(each) + ' - output')
    GPIO.setup(each, GPIO.OUT, initial=False)


##############################################################
##############################################################
##############################################################
def set_gpio_state(gpio, state):
    if gpio != ch_relay and gpio != ch_led:
        return False
    else:
        if gpio == 'heating':
            GPIO.output(ch_relay, state)
            GPIO.output(ch_led, not state)
            log('set CH to ' + str(state))
        if gpio == ch_relay:
            GPIO.output(gpio, state)
            log('set relay to ' + str(state))
        else:
            GPIO.output(gpio, not state)
            log('set led to ' + str(not state))
        return True


###############################################################


def initial_test():
    set_gpio_state(ch_relay, True)
    time.sleep(1)
    set_gpio_state(ch_relay, False)
    time.sleep(0.25)
    set_gpio_state(ch_led, False)
    time.sleep(1)
    set_gpio_state(ch_led, True)
    time.sleep(0.5)
    return True


##############################################################


def get_gpio_state(gpio):
    if gpio != ch_relay and gpio != ch_led:
        return False
    else:
        log('gpio state - ' + str(GPIO.input(gpio)))
        return GPIO.input(gpio)


#############################################################


def button_press(channel):
    press_time = {}
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
    set_gpio_state(ch_led, True)
    for x in range(10):
        time.sleep(1)
        set_gpio_state(ch_led, False)
        time.sleep(type_flash)
        set_gpio_state(ch_led, True)
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
                ' /home/pinest/Documents/livingroom'], shell=True)
            log('mounted')
        filename = (
            '/home/pinest/Documents/livingroom/Current_Temp/livingroom_temp.csv')
        with open(filename) as f:
            current_t = f.read().split(',')
        log('Current temperature in the living room is ' + str(current_t[1]))
        return float(current_t[1])
    elif location == 'utility':
        filename = '/home/pinest/Documents/Current_Temp/utility_temp.csv'
        f = open(filename)
        current_t = f.read().split(',')
        f.close()
        log('Current temperature in the utility is ' + str(current_t[1]))
        return float(current_t[1])


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

last_call = datetime.strptime('2015-01-01', '%Y-%m-%d')


def get_schedule(override=False):
    global call
    global testing
    global last_call
    call = datetime.now()
    call_delta = (call - last_call).total_seconds() / 1.0
    if call_delta >= 60 or override:
        credentials = get_credentials()
        http = credentials.authorize(httplib2.Http())
        service = discovery.build('calendar', 'v3', http=http)
        now = datetime.utcnow()
        now_utc = datetime.utcnow().isoformat()[:19] + 'Z'
        datetime_end = now.replace(hour=23, minute=59, second=59)
        end = datetime_end.isoformat()[:19] + 'Z'
        events_results = service.events().list(
                calendarId='primary', timeMin=now_utc, timeMax=end,
                orderBy='startTime', singleEvents=True).execute()
        events = events_results.get('items', [])
        last_call = datetime.now()
        if not events:
            log('No upcoming events found.')
            return False, None
        i = 0
        for event in events:
            start = datetime.strptime((str(event['start'].get('dateTime'))), '%Y-%m-%dT%H:%M:%SZ')
            calendar_temp = int(event['summary'])
            stop = datetime.strptime((str(event['end'].get('dateTime'))), '%Y-%m-%dT%H:%M:%SZ')
            schedule = {}
            schedule.setdefault(i, [])
            schedule[i].append([start, calendar_temp, stop])
            i += 1
            log('loaded schedule - ' + str(schedule))
            if schedule[0][0][0] < now < schedule[0][0][2]:
                return True, schedule
        if not override:
            return True, schedule
        else:
            return False, None
    else:
        return False, None


########################################################################


def timer(set_time, key=None, schedule=False):
    log('timer')
    now = time.time()
    if not schedule:
        log('not schedule')
        time_left = set_time
        while not get_schedule() and time_left > 0:
            if not get_gpio_state(ch_relay):
                set_gpio_state('heating', True)
            current_temp_living_room = current_temp('living_room')
            log('current temp = ' + str(current_temp_living_room))
            if current_temp_living_room >= 20:
                log('current temperature over 20')
                while current_temp('living_room') >= 19:
                    log('Turning heating off until temperature drops 2 degrees')
                    if get_gpio_state(ch_relay):
                        set_gpio_state('heating', False)
                    time.sleep(60)
                    time_left -= 1
            time.sleep(60)
            time_left -= 1
        return True
    else:
        log(str(get_schedule(override=True)[0]))
        time_left = set_time
        while get_schedule(override=True)[0] and time_left > 0:
            log(str(time_left))
            if not get_gpio_state(ch_relay):
                set_gpio_state('heating', True)
            current_temp_living_room = current_temp('living_room')
            log('current temp = ' + str(current_temp_living_room))
            if current_temp_living_room >= (schedule[key][0][1] + 0.0):
                log('current temperature over set temperature')
                while current_temp('living_room') >= ((schedule[key][0][1]) - 2.0):
                    log('Turning heating off until temperature drops 2 degrees')
                    if get_gpio_state(ch_relay):
                        set_gpio_state('heating', False)
                    time.sleep(60)
                    time_left -= 1
            time.sleep(60)
            time_left -= 1
        return True
    return False





####################################################################################
initial_test_state = 0
detecting = False


def main():
    global detecting
    log('detecting - ' + str(detecting))
    if not detecting:
        GPIO.add_event_detect(ch_switch, GPIO.FALLING,
                              callback=button_activated, bouncetime=1000)
        detecting = True
    try:
        if initial_test_state == 0:
            initial_test()
        while True:
            had_event = False
            heating_schedule = get_schedule()
            log('checked schedule in main')
            if heating_schedule[0]:
                heating_schedule = heating_schedule[1]
                log(str(heating_schedule)+' '+str(range(len(heating_schedule.keys()) - 1)))
                now = datetime.now()
                log('trying')
                if len(heating_schedule.keys()) > 2:
                    for i in range(len(heating_schedule.keys()) - 1):
                        log(str(i))
                        try:
                            if heating_schedule[i][0][0] <= now < heating_schedule[i][0][2]:
                                key = i
                                log('event scheduled now: ' + str(key))
                                break
                        except KeyError:
                            log('key = 0')
                            if heating_schedule[0][0][0] <= now < heating_schedule[0][0][2]:
                                key = 0
                            else:
                                key = None
                else:
                    if heating_schedule[0][0][0] <= now < heating_schedule[0][0][2]:
                        key = 0
                    else:
                        key = None
                set_time = int((heating_schedule[key][0][2] - now).total_seconds() / 60)
                timer(set_time, key=key, schedule=heating_schedule)
                had_event = True
            if not had_event:
                log('sleeping...')
                time.sleep(60)
    except KeyboardInterrupt:
        log('Stopped by user')
    finally:
        log('Cleaning up')
        GPIO.cleanup()

#############################################################


def button_activated(ch_switch):
    global detecting
    detecting = False
    if not get_schedule(override=True)[1]:
        if GPIO.event_detected(ch_switch):
            log('Checking if button pressed')
            real_press, time_pressed = button_press(ch_switch)
            if real_press and 1.5 < time_pressed < 20.0:
                while True:
                    if not timer(60,key=None,schedule=False):
                        detecting = False
                        break
            else:
                log('error flash 1')
                error_flash(1)

        else:
            log('error flash 2')
            error_flash(1)

#####################################################################


if __name__ == "__main__":
    main()
