# -*- coding: utf-8 -*-
"""
Sends test message
"""
import requests
import datetime


json = {
    'raspi_serial': 'ERROR000000000',
    'ibeacon_serial': 'b3de1433880f020106030220fe07fffe',
    'in_time': (datetime.datetime.now() - datetime.timedelta(minutes=1)).isoformat(),
    'out_time': datetime.datetime.now().isoformat()
}

res = requests.post('http://localhost:5000/api/add_message/', json=json)
if res.ok:
    print(res)