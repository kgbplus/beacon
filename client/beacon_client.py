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
import pickle
import os
from collections import deque

import bluetooth._bluetooth as bluez

SERVER_URL = 'http://192.168.43.43/api/messages/'
# SERVER_URL = 'http://127.0.0.1/api/messages/'
TIMEOUT = 10
DIST_ZERO = 30
SMA_N = 5
ALLOWED_MAJOR = ['1',]
SAVE_FILE = 'beacons.pkl'
DEBUG = False


class Beacons():
    """
    Beacons temporary storage structure
    dict[beacon] = [in_time, last_seen_time, min_dist, last(deque(5))]
    """

    def __init__(self):
        try:
            with open(SAVE_FILE, 'rb') as f:
                self.beacons = pickle.load(f)
            os.remove(SAVE_FILE)
        except:
            self.beacons = {}

    def in_time(self, beacon):
        return self.beacons[beacon][0]

    def out_time(self, beacon):
        return self.beacons[beacon][1]

    def min_dist(self, beacon):
        return self.beacons[beacon][2]

    def add(self, beacon, time, dist):
        "Updates beacon if exist, creates new beacon otherwise"
        try:
            in_time, last_seen_time, min_dist, last = self.beacons.pop(beacon)
            last.append(dist)
            m_average = sum(last) // len(last)
            if DEBUG:
                print("{}, dist = {}, moving_average = {}".format(beacon, dist, m_average))
            self.beacons[beacon] = [in_time, time, m_average if m_average < min_dist else min_dist, last]
        except:
            if DEBUG:
                print("{}, dist = {}, moving_average = NEW".format(beacon, dist))
            self.beacons[beacon] = [time, time, dist, deque([dist], SMA_N)]
        self.save()

    def remove(self, beacon):
        "Removes beacon"
        try:
            self.beacons.pop(beacon)
        except:
            pass
        self.save()

    def save(self):
        # Try to save beacons
        try:
            with open(SAVE_FILE, 'wb') as f:
                pickle.dump(self.beacons, f, protocol=pickle.HIGHEST_PROTOCOL)
        except:
            pass

    def check(self, beacon, time):
        "Returns True if beacon exists and was seen more then TIMEOUT seconds ago"
        try:
            if (time - self.beacons[beacon][1]).seconds > TIMEOUT:
                return True
        except:
            pass
        return False

    def ready_to_send(self):
        "Returns iterable with ready-to-send beacons"
        return [b for b in self.beacons
                if self.check(b, datetime.datetime.now())]


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


def check_and_send(beacons):
    "Check if beacon wasn't seen during TIMEOUT and send it to server"
    while True:
        for beacon in beacons.ready_to_send():
            uuid, major, minor = beacon.split(',')[1:4]
            json = {
                'raspi_serial': getserial(),
                'ibeacon_uuid': uuid,
                'ibeacon_major': str(major),
                'ibeacon_minor': str(minor),
                'in_time': beacons.in_time(beacon).isoformat(),
                'out_time': beacons.out_time(beacon).isoformat(),
                'min_dist': str(beacons.min_dist(beacon))
            }
            if DEBUG:
                print("sending {},{},{}; min_dist = {}".format(uuid, major, minor, beacons.min_dist(beacon)))
            res = requests.post(SERVER_URL, json=json)
            if res.ok:
                if DEBUG:
                    print("sent {},{},{}; min_dist = {}".format(uuid, major, minor, beacons.min_dist(beacon)))
                beacons.remove(beacon)

        time.sleep(TIMEOUT)


def correct_time():
    try:
        import ntplib
        client = ntplib.NTPClient()
        response = client.request('pool.ntp.org')
        os.system('date ' + time.strftime('%m%d%H%M%Y.%S', time.localtime(response.tx_time)))
    except:
        print('Could not sync with time server.')


def main(*args, **kwargs):
    correct_time()

    beacons = Beacons()

    timer_thread = threading.Thread(target=check_and_send, args=(beacons,))
    timer_thread.daemon = True
    timer_thread.start()

    dev_id = 0
    try:
        sock = bluez.hci_open_dev(dev_id)
        blescan.hci_le_set_scan_parameters(sock)
        blescan.hci_enable_le_scan(sock)
        if DEBUG:
            print("ble thread started")
    except Exception as e:
        print("error accessing bluetooth device: {}".format(e[1]))
        sys.exit(1)

    try:
        while True:
            returnedList = blescan.parse_events(sock, 1)
            for beacon in returnedList:
                uuid, major, minor = beacon.split(',')[1:4]
                if major in ALLOWED_MAJOR:
                    beacon_id = beacon[:-8]
                    beacon_datetime = datetime.datetime.now()
                    beacon_dist = int(beacon[-2:]) - DIST_ZERO
                    beacons.add(beacon_id, beacon_datetime, beacon_dist)
    except KeyboardInterrupt:
        print("\nCtrl-C pressed")
        sys.exit()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
