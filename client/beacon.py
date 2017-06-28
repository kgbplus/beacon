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

import pickle
import datetime

import const
import logger

logger = logger.get_logger(__name__)


class Beacons():
    """
    Beacons temporary storage structure
    dict[beacon] = [in_time, last_seen_time, min_dist, last(deque(5))]
    """

    def __init__(self):
        self.modified = False

        try:
            with open(const.SAVE_FILE, 'rb') as f:
                self.beacons = pickle.load(f)
        except:
            logger.warning('Cannot load beacons')
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
            logger.info("{}, dist = {} NEW".format(beacon, dist))
            self.beacons[beacon] = [time, time, dist, time]
        finally:
            self.modified = True

    def add_preserve(self, beacon):
        "Preserves ready-to-send message"
        try:
            beacon_id = beacon + ',' + self.min_time(beacon).isoformat() + 'save'
            in_time, last_seen_time, min_dist, min_time = self.beacons.pop(beacon)
            logger.debug("preserve {}, min_dist = {}, min_time = {}".format(beacon, min_dist, min_time))
            self.beacons[beacon_id] = [in_time, last_seen_time, min_dist, min_time]
            self.modified = True
        except Exception as e:
            logger.error("exception in preserve {}".format(beacon), exc_info=True)

    def remove(self, beacon):
        "Removes beacon"
        try:
            self.beacons.pop(beacon)
            self.modified = True
        except:
            pass

    def save(self):
        "Try to save beacons if modified"
        try:
            if self.modified:
                with open(const.SAVE_FILE, 'wb') as f:
                    pickle.dump(self.beacons, f, protocol=pickle.HIGHEST_PROTOCOL)
                    f.flush()
                self.modified = False
                logger.debug("{} records saved to pkl".format(len(self.beacons)))
        except:
            logger.error("pkl save error!")

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
