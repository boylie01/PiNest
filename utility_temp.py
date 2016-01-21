from datetime import datetime
import time
import os
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
logging.basicConfig()


def temp():
    id = '28-0000073e62fa'
    deviceFile = '/sys/bus/w1/devices/' + id + '/w1_slave'
    f = open(deviceFile, 'r')
    linesa = f.readlines()
    f.close()
    
    linesb = linesa
    check = linesb[0].strip()[-1]
    if check != 'S':
        return 'error'
    if check == 'S':
        tempPos = linesb[1].find('t=')
        temp = float(linesb[1][tempPos+2:]) / 1000.0

    now = datetime.now()
    fileName = '/home/pinest/Documents/Current_Temp/utility_temp.csv'
    fileWrite = open(fileName, 'w')
    timestamp = now.strftime("%H:%M")
    output = str(timestamp) + " , " + str(temp) + '\n'
    fileWrite.write(output) 
    fileWrite.close()
    time.sleep(5)

if __name__ == '__main__':
    scheduler = BlockingScheduler()
    scheduler.add_job(temp, 'cron', minute= '0,10,20,30,40,50')

    try:
        scheduler.start()
    except(KeyboardInterrupt):
        pass
