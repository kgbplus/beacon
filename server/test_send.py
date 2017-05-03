# -*- coding: utf-8 -*-
"""
Sends test message
"""
import requests
import datetime


SERVER_URL = 'http://10.0.100.102:5000/api/add_message/'

json = {
    'raspi_serial': 'ERROR000000000',
    'ibeacon_uuid': 'b3de1433880f020106030220fe07fffe',
    'ibeacon_major': 1,
    'ibeacon_minor': 5555,
    'in_time': (datetime.datetime.now() - datetime.timedelta(minutes=1)).isoformat(),
    'out_time': datetime.datetime.now().isoformat()
}

res = requests.post(SERVER_URL, json=json)
if res.ok:
    print(res)