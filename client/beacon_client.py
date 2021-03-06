# -*- coding: utf-8 -*-

"""
Event server simple client
Waits for I-Beacons and sends messages
Temporary stores messages in file


MIT License

Copyright (c) 2017 Roman Mindlin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import blescan
import sys
import time
import datetime
import requests
import threading
import math
import os
import const

import bluetooth._bluetooth as bluez

from beacon import Beacons
import processors
import logger

logger = logger.get_logger(__name__)


def getrange(txPower, rssi):
    "https://stackoverflow.com/questions/20416218/understanding-ibeacon-distancing"
    if txPower == 0:
        txPower = 1
    ratio = float(rssi) / txPower
    if (ratio < 1.0):
        return round(math.pow(ratio, 10))
    else:
        distance = (0.89976) * math.pow(ratio, 7.7095) + 0.111
    return round(distance)


def getserial():
    "Extract serial from cpuinfo file"
    cpuserial = "0000000000000000"
    try:
        f = open('/proc/cpuinfo', 'r')
        for line in f:
            if line[0:6] == 'Serial':
                cpuserial = line[10:26]
        f.close()
    except:
        cpuserial = "ERROR000000000"
    return cpuserial


def check_and_send(beacons, processor):
    "Check if beacon wasn't seen during TIMEOUT and send it to server"
    while True:
        ready_to_send = list(beacons.ready_to_send())
        for beacon in ready_to_send:
            if beacon[-4:] == 'save':
                uuid, major, minor = beacon.split(',')[1:4]
                json = {
                    'raspi_serial': getserial(),
                    'ibeacon_uuid': uuid,
                    'ibeacon_major': str(major),
                    'ibeacon_minor': str(minor),
                    'in_time': beacons.in_time(beacon).isoformat(),
                    'out_time': beacons.out_time(beacon).isoformat(),
                    'min_dist': str(beacons.min_dist(beacon)),
                    'min_time': beacons.min_time(beacon).isoformat()
                }
                logger.debug("sending {},{},{}; min_dist = {}".format(uuid, major, minor, beacons.min_dist(beacon)))
                try:
                    res = requests.post(const.SERVER_URL, json=json, timeout=2)
                    if res.ok:
                        logger.info("sent {},{},{}; min_dist = {}".format(uuid, major, minor, beacons.min_dist(beacon)))
                        beacons.remove(beacon)
                        processor.clear(beacon)
                except:
                    logger.debug('Server not responding')
            else:
                beacons.add_preserve(beacon)
        time.sleep(const.TIMEOUT)


def save_pkl(beacons):
    "Saves beacons to file periodically"
    while True:
        beacons.save()
        time.sleep(const.SAVE_TIMEOUT)


def correct_time():
    "NTP client"
    try:
        import ntplib
        client = ntplib.NTPClient()
        response = client.request('pool.ntp.org')
        os.system('date ' + time.strftime('%m%d%H%M%Y.%S', time.localtime(response.tx_time)))
        if const.RTC:
            os.system('hwclock -w')  # Sync hardware RTC
        logger.info('Time sync success')
    except:
        logger.error('Could not sync with time server.', exc_info=True)


def start(*args, **kwargs):
    "Main loop"
    logger.info("Raspberry serial: {}".format(getserial()))

    if const.DUMP:
        csv = open('data.csv', 'w')

    if const.TIME_SYNC:
        logger.info("Waiting for time sync")
        time.sleep(10)
        correct_time()

    beacons = Beacons()
    # processor = processors.Kalman()
    processor = processors.OneSecondAverage()

    timer_thread = threading.Thread(target=check_and_send, args=(beacons, processor))
    timer_thread.daemon = True
    timer_thread.start()

    save_thread = threading.Thread(target=save_pkl, args=(beacons,))
    save_thread.daemon = True
    save_thread.start()

    dev_id = 0
    try:
        sock = bluez.hci_open_dev(dev_id)
        blescan.hci_le_set_scan_parameters(sock)
        blescan.hci_enable_le_scan(sock)
        logger.info("ble thread started")
    except Exception as e:
        logger.error('Error accessing bluetooth device', exc_info=True)
        sys.exit(1)

    try:
        while True:
            returnedList = blescan.parse_events(sock, 1)
            for beacon in returnedList:
                uuid, major, minor = beacon.split(',')[1:4]
                if major in const.ALLOWED_MAJOR:
                    beacon_id = beacon[:-8]
                    if beacon_id[-2:] == ',,':  # double comma at end of string
                        beacon_id = beacon_id[:-1]
                    beacon_datetime = datetime.datetime.now()
                    txpower = int(beacon.split(',')[4])
                    rssi = int(beacon.split(',')[5])

                    rssi = -99 if rssi < -99 else rssi # rssi peak fix

                    rssi_filtered = processor.filter(beacon_id, rssi)
                    if rssi_filtered is None:
                        continue

                    beacon_dist = getrange(txpower, rssi_filtered)

                    if const.DUMP:
                        csv.write(str(beacon_datetime) + ',')
                        csv.write(beacon + ',')
                        csv.write('{:.0f}'.format(beacon_dist) + '\n')

                    if beacon_dist < const.MAX_RANGE:  # maximum range
                        beacons.add(beacon_id, beacon_datetime, beacon_dist)
    except KeyboardInterrupt:
        logger.warning("Ctrl-C pressed")
        if const.DUMP:
            csv.close()
        sys.exit()


if __name__ == "__main__":
    sys.exit(start(sys.argv))
