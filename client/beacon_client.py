import blescan
import sys
import time
import datetime
import requests
import threading

import bluetooth._bluetooth as bluez


SERVER_URL = 'http://10.0.100.102:5000/api/add_message/'
TIMEOUT = 10
DEBUG = True


class Beacons():
    '''
    Beacons temporary storage structure
    dict[beacon] = [in_time, last_seen_time]
    '''
    def __init__(self):
        self.beacons = {}

    def in_time(self, beacon):
        return self.beacons[beacon][0]

    def out_time(self, beacon):
        return self.beacons[beacon][1]

    def add(self, beacon, time):
        '''
        Updates beacon if exist,
        creates new beacon otherwise
        '''
        try:
            in_time, last_seen_time = self.beacons.pop(beacon)
            self.beacons[beacon] = [in_time, time]
        except:
            self.beacons[beacon] = [time, time]

    def remove(self, beacon):
        '''
        Removes beacon
        '''
        try:
            self.beacons.pop(beacon)
        except:
            pass


    def check(self, beacon, time):
        '''
        Returns True if beacon exists and was seen more then TIMEOUT seconds ago
        '''
        try:
            if (time - self.beacons[beacon][1]).seconds > TIMEOUT:
                return True
        except:
            pass
        return False

    def ready_to_send(self):
        '''
        Returns iterable with ready-to-send beacons
        '''
        return [b for b in self.beacons
                    if self.check(b, datetime.datetime.now())]


def getserial():
    # Extract serial from cpuinfo file
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
    while True:
        for beacon in beacons.ready_to_send():
            uuid, major, minor = beacon.split(',')[1:4]
            json = {
                'raspi_serial': getserial(),
                'ibeacon_uuid': uuid,
                'ibeacon_major': str(major),
                'ibeacon_minor': str(minor),
                'in_time': beacons.in_time(beacon).isoformat(),
                'out_time': beacons.out_time(beacon).isoformat()
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
                beacons.add(beacon[:-8], datetime.datetime.now())
    except KeyboardInterrupt:
        print("\nCtrl-C pressed")
        sys.exit()


if __name__== "__main__":
    sys.exit(main(sys.argv))
