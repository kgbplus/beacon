import blescan
import sys
import time
import datetime
import requests
import threading
from collections import deque

import bluetooth._bluetooth as bluez


#SERVER_URL = 'http://10.0.100.102/api/add_message/'
SERVER_URL = 'http://127.0.0.1/api/add_message/'
TIMEOUT = 2
DEBUG = True


class Beacons():
    '''
    Beacons temporary storage structure
    dict[beacon] = [in_time, last_seen_time, min_dist, last(deque(5))]
    '''
    def __init__(self):
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
            self.beacons[beacon] = [in_time, time, m_average if m_average < min_dist else min_dist, last]
        except:
            self.beacons[beacon] = [time, time, dist, deque([dist],5)]

    def remove(self, beacon):
        "Removes beacon"
        try:
            self.beacons.pop(beacon)
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
        f = open('/proc/cpuinfo','r')
        for line in f:
            if line[0:6]=='Serial':
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
            if minor != '9621':
                continue
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
                print("sending {}".format(beacon))
                print(json)
            res = requests.post(SERVER_URL, json=json)
            if res.ok:
                print("sent")
                beacons.remove(beacon)

        time.sleep(TIMEOUT)


def main(*args, **kwargs):
    beacons = Beacons()

    timer_thread = threading.Thread(target = check_and_send, args=(beacons,))
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
                if DEBUG:
                    print(beacon)
                beacon_id = beacon[:-8]
                beacon_datetime = datetime.datetime.now()
                beacon_dist = int(beacon[-2:])
                beacons.add(beacon_id, beacon_datetime, beacon_dist)
    except KeyboardInterrupt:
        print("\nCtrl-C pressed")
        sys.exit()


if __name__== "__main__":
    sys.exit(main(sys.argv))
