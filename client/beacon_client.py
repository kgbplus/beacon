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
import math
import os
import logging
import const

import bluetooth._bluetooth as bluez

"Setup logging"
LOG_LEVEL = logging.DEBUG

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

file_handler = logging.FileHandler(const.LOG_FILE)
file_handler.setLevel(LOG_LEVEL)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(LOG_LEVEL)

formatter = logging.Formatter('%(asctime)s: %(name)s [%(levelname)s] %(message)s')
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)


class Beacons():
    """
    Beacons temporary storage structure
    dict[beacon] = [in_time, last_seen_time, min_dist, last(deque(5))]
    """

    def __init__(self):
        try:
            with open(const.SAVE_FILE, 'rb') as f:
                self.beacons = pickle.load(f)
        except:
            logging.warning('Cannot load beacons')
            self.beacons = {}

    def in_time(self, beacon):
        return self.beacons[beacon][0]

    def out_time(self, beacon):
        return self.beacons[beacon][1]

    def min_dist(self, beacon):
        return self.beacons[beacon][2]

    def min_time(self, beacon):
        return self.beacons[beacon][3]

    def add(self, beacon, time, dist):
        "Updates beacon if exist, creates new beacon otherwise"
        try:
            in_time, last_seen_time, min_dist, min_time = self.beacons.pop(beacon)
            new_min_dist = dist if dist < min_dist else min_dist
            new_min_time = time if dist < min_dist else min_time
            logger.debug("{}, dist = {}".format(beacon, dist))
            self.beacons[beacon] = [in_time, time, new_min_dist, new_min_time]
        except:
            logger.debug("{}, dist = {} NEW".format(beacon, dist))
            self.beacons[beacon] = [time, time, dist, time]
        self.save()

    def add_preserve(self, beacon):
        "Preserves ready-to-send message"
        try:
            beacon_id = beacon + ',' + self.min_time(beacon).isoformat() + 'save'
            in_time, last_seen_time, min_dist, min_time = self.beacons.pop(beacon)
            logger.debug("preserve {}, min_dist = {}, min_time = {}".format(beacon, min_dist, min_time))
            self.beacons[beacon_id] = [in_time, last_seen_time, min_dist, min_time]
        except Exception as e:
            logger.error("exception in preserve {}".format(beacon), exc_info=True)
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
            with open(const.SAVE_FILE, 'wb') as f:
                pickle.dump(self.beacons, f, protocol=pickle.HIGHEST_PROTOCOL)
        except:
            pass

    def check(self, beacon, time):
        "Returns True if beacon exists and was seen more then TIMEOUT seconds ago"
        try:
            if (time - self.beacons[beacon][1]).seconds > const.TIMEOUT:
                return True
        except:
            pass
        return False

    def ready_to_send(self):
        "Returns iterable with ready-to-send beacons"
        return [b for b in self.beacons
                if self.check(b, datetime.datetime.now())]


class Kalman():
    """
    Implements Kalman filter for RSSI measuring
    """

    def __init__(self):
        self.beacons = {}

    def filter(self, beacon, rssi):
        """
        Takes beacon id and rssi, stores rssi in array and calculate rssi a posteri estimate
        Didn't store its state due to memory restrictions (large number of beacons), 
        but calculate all values every time (high cpu load)
        """
        try:
            self.beacons[beacon].append(rssi)
            z = self.beacons[beacon]

            # intial parameters
            n_iter = len(z)
            Q = 1e-5  # process variance
            R = 0.1 ** 4  # estimate of measurement variance, change to see effect

            # allocate space for arrays
            xhat = list()  # a posteri estimate of x
            P = list()  # a posteri error estimate
            xhatminus = [0]  # a priori estimate of x
            Pminus = [0]  # a priori error estimate
            K = [0]  # gain or blending factor

            # intial guesses
            xhat.append(-40.0)
            P.append(1.0)

            for k in range(1, n_iter):
                # time update
                xhatminus.append(xhat[k - 1])
                Pminus.append(P[k - 1] + Q)

                # measurement update
                K.append(Pminus[k] / (Pminus[k] + R))
                xhat.append(xhatminus[k] + K[k] * (z[k] - xhatminus[k]))
                P.append((1 - K[k]) * Pminus[k])

            return int(xhat[-1])
        except:
            self.beacons[beacon] = [rssi]
            return rssi


def getrange(txPower, rssi):
    "https://stackoverflow.com/questions/20416218/understanding-ibeacon-distancing"
    if txPower == 0:
        txPower = 1
    ratio = rssi * 1.0 / txPower
    if (ratio < 1.0):
        return round(math.pow(ratio, 10))
    else:
        accuracy = (0.89976) * math.pow(ratio, 7.7095) + 0.111
    return round(accuracy)


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
                except Exception as e:
                    logger.error('Server not responding', exc_info=True)
            else:
                beacons.add_preserve(beacon)

        time.sleep(const.TIMEOUT)


def correct_time():
    "NTP client"
    try:
        import ntplib
        client = ntplib.NTPClient()
        response = client.request('pool.ntp.org')
        os.system('date ' + time.strftime('%m%d%H%M%Y.%S', time.localtime(response.tx_time)))
        logger.info('Time sync success')
    except:
        logger.error('Could not sync with time server.', exc_info=True)


def start(*args, **kwargs):
    "Main loop"
    logger.info("Raspberry serial: {}".format(getserial()))

    if const.TIME_SYNC:
        logger.info("Waiting for time sync")
        time.sleep(10)
        correct_time()

    beacons = Beacons()
    kf = Kalman()

    timer_thread = threading.Thread(target=check_and_send, args=(beacons,))
    timer_thread.daemon = True
    timer_thread.start()

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
                    beacon_datetime = datetime.datetime.now()
                    txpower = int(beacon.split(',')[4])
                    rssi = int(beacon.split(',')[5])
                    rssi_filtered = kf.filter(beacon_id, rssi)
                    beacon_dist = getrange(txpower, rssi_filtered)
                    beacons.add(beacon_id, beacon_datetime, beacon_dist)
    except KeyboardInterrupt:
        logger.warning("Ctrl-C pressed")
        sys.exit()


if __name__ == "__main__":
    sys.exit(start(sys.argv))
