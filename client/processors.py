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

import datetime

from collections import deque


class Kalman(object):
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
            if self.beacons.get(beacon) is None:
                self.beacons[beacon] = deque(maxlen=30)
            self.beacons[beacon].append(rssi)
            z = self.beacons[beacon]

            # intial parameters
            n_iter = len(z)
            Q = 1e-6  # process variance
            R = 0.1 ** 3  # estimate of measurement variance, change to see effect

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

    def clear(self, beacon):
        """
        Delete lost beacon records
        """
        self.beacons.pop(beacon, None)


class OneSecondAverage(object):
    """
    Calculates average for one second
    """

    def __init__(self):
        self.beacons = {}

    def filter(self, beacon, rssi):
        try:
            if self.beacons.get(beacon) is None:
                self.beacons[beacon] = deque(maxlen=30), datetime.datetime.now()
            else:
                d, t = self.beacons[beacon]
                if datetime.datetime.now() - t > datetime.timedelta(seconds=1):
                    rssi_average = sum(d) // len(d)
                    d.clear()
                    self.beacons[beacon] = d, datetime.datetime.now()
                    return rssi_average
                else:
                    d.append(rssi)
                    return None

        except:
            return None

    def clear(self, beacon):
        """
        Delete lost beacon records
        """
        self.beacons.pop(beacon, None)
