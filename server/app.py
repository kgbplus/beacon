# -*- coding: utf-8 -*-

"""
Simple server
Takes i-beacon read data with POST method
Return summary data with GET


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

from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import aliased
from flask_migrate import Migrate
import os
from dateutil import parser
import sys

basedir = os.path.abspath(os.path.dirname(__file__))

if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding("utf-8")

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data.sqlite3')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

"""
 ****************** MODELS ******************
"""


class Beacon(db.Model):
    "I-beacon data model"
    __tablename__ = 'beacons'

    id = db.Column(db.Integer, primary_key=True)
    raspi_serial = db.Column(db.String(14), index=True)
    ibeacon_uuid = db.Column(db.String(32))
    ibeacon_major = db.Column(db.Integer, index=True)
    ibeacon_minor = db.Column(db.Integer, index=True)
    in_time = db.Column(db.DateTime, index=True)
    out_time = db.Column(db.DateTime, index=True)
    min_dist = db.Column(db.Integer)
    min_time = db.Column(db.DateTime)

    @property
    def serialize(self):
        "Return object data in easily serializeable format"
        return {
            'id': self.id,
            'raspi_serial': self.raspi_serial,
            'ibeacon_uuid': self.ibeacon_uuid,
            'ibeacon_major': self.ibeacon_major,
            'ibeacon_minor': self.ibeacon_minor,
            'in_time': self.in_time.isoformat(),
            'out_time': self.out_time.isoformat(),
            'min_dist': self.min_dist,
            'min_time': self.min_time.isoformat()
        }


class Gate(db.Model):
    "I-Beacon agents pairs"
    __tablename__ = 'gates'

    id = db.Column(db.Integer, primary_key=True)
    raspi_serial_left = db.Column(db.String(14), index=True)
    raspi_serial_right = db.Column(db.String(14), index=True)
    distance = db.Column(db.Integer)

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id': self.id,
            'raspi_serial_left': self.raspi_serial_left,
            'raspi_serial_right': self.raspi_serial_right,
            'distance': self.distance
        }


class Event(db.Model):
    "Gate passing through event"
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    gate_id = db.Column(db.Integer, index=True)
    ibeacon_uuid = db.Column(db.String(32))
    ibeacon_major = db.Column(db.Integer)
    ibeacon_minor = db.Column(db.Integer)
    in_time = db.Column(db.DateTime, index=True)
    out_time = db.Column(db.DateTime, index=True)
    min_time_left = db.Column(db.DateTime)
    min_time_right = db.Column(db.DateTime)
    course = db.Column(db.Enum('left', 'center', 'right', 'wide'))

    @property
    def serialize(self):
        "Return object data in easily serializeable format"
        return {
            'id': self.id,
            'gate_id': self.gate_id,
            'ibeacon_uuid': self.ibeacon_uuid,
            'ibeacon_major': self.ibeacon_major,
            'ibeacon_minor': self.ibeacon_minor,
            'in_time': self.in_time.isoformat(),
            'out_time': self.out_time.isoformat(),
            'min_time_left': self.min_time_left.isoformat(),
            'min_time_right': self.min_time_right.isoformat(),
            'course': self.course
        }


"""
 ****************** MESSAGES ******************
"""


@app.route('/api/messages/', methods=['GET'])
def get_messages():
    "Sends back all messages"
    content = Beacon.query.all()
    return jsonify([i.serialize for i in content]), 200


@app.route('/api/messages/', methods=['POST'])
def add_message():
    "Inputs new message and saves it in db"
    content = request.get_json(silent=True, force=False)
    if content:
        new_message = Beacon(raspi_serial=content.get('raspi_serial'),
                             ibeacon_uuid=content.get('ibeacon_uuid'),
                             ibeacon_major=content.get('ibeacon_major'),
                             ibeacon_minor=content.get('ibeacon_minor'),
                             in_time=parser.parse(content.get('in_time')),
                             out_time=parser.parse(content.get('out_time')),
                             min_dist=int(float(content.get('min_dist'))), 
                             min_time=parser.parse(content.get('min_time')))
        # check if same record exists
        if db.session.query(Beacon.id).filter((Beacon.raspi_serial == new_message.raspi_serial) &
                                                      (Beacon.ibeacon_uuid == new_message.ibeacon_uuid) &
                                                      (Beacon.ibeacon_major == new_message.ibeacon_major) &
                                                      (Beacon.ibeacon_minor == new_message.ibeacon_minor) &
                                                      (Beacon.in_time == new_message.in_time) &
                                                      (Beacon.out_time == new_message.out_time) &
                                                      (Beacon.min_dist == new_message.min_dist) &
                                                      (Beacon.min_time == new_message.min_time)).count() == 0:
            db.session.add(new_message)
            return "<h1>Ok</h1>", 200
        else:
            return "<h1>Error</h1>", 400
    else:
        return "<h1>Error</h1>", 400


@app.route('/api/messages/<int:id>', methods=['PUT'])
def update_message(id):
    "Update message with given id"
    content = request.get_json(silent=True, force=False)
    if content:
        try:
            message = Beacon.query.filter(Beacon.id == id).first()
            message.raspi_serial = content.get('raspi_serial')
            message.ibeacon_uuid = content.get('ibeacon_uuid')
            message.ibeacon_major = content.get('ibeacon_major')
            message.ibeacon_minor = content.get('ibeacon_minor')
            message.in_time = parser.parse(content.get('in_time'))
            message.out_time = parser.parse(content.get('out_time'))
            message.min_dist = int(content.get('min_dist'))
            message.min_time = parser.parse(content.get('min_time'))

            db.session.commit()
        except:
            return "<h1>Error</h1>", 404
    else:
        return "<h1>Error</h1>", 400
    return "<h1>Ok</h1>", 200


@app.route('/api/messages/<int:id>', methods=['DELETE'])
def delete_message(id):
    "Delete message with given id"
    try:
        Beacon.query.filter(Beacon.id == id).delete(synchronize_session='evaluate')
    except:
        return "<h1>Error</h1>", 404
    return "<h1>Ok</h1>", 200


"""
 ****************** GATES ******************
"""


@app.route('/api/gates/', methods=['GET'])
def get_gates():
    "Sends back all gates"
    content = Gate.query.all()
    return jsonify([i.serialize for i in content]), 200


@app.route('/api/gates/', methods=['POST'])
def add_gate():
    "Inputs new gate and saves it in db"
    content = request.get_json(silent=True, force=False)
    if content:
        new_gate = Gate(raspi_serial_left=content.get('raspi_serial_left'),
                        raspi_serial_right=content.get('raspi_serial_right'),
                        distance=content.get('distance'))
        # check if same record exists
        if db.session.query(Gate.id).filter((Gate.raspi_serial_left == new_gate.raspi_serial_left) &
                                                    (Gate.raspi_serial_right == new_gate.raspi_serial_right) &
                                                    (Gate.distance == new_gate.distance)).count() == 0:
            db.session.add(new_gate)
            return "<h1>Ok</h1>", 200
        else:
            return "<h1>Error</h1>", 400
    else:
        return "<h1>Error</h1>", 400


@app.route('/api/gates/<int:id>', methods=['PUT'])
def update_gate(id):
    "Update gate with given id"
    content = request.get_json(silent=True, force=False)
    if content:
        try:
            gate = Gate.query.filter(Gate.id == id).first()
            gate.raspi_serial_left = content.get('raspi_serial_left')
            gate.raspi_serial_right = content.get('raspi_serial_right')
            gate.distance = content.get('distance')

            db.session.commit()
        except:
            return "<h1>Error</h1>", 404
    else:
        return "<h1>Error</h1>", 400
    return "<h1>Ok</h1>", 200


"""
 ****************** EVENTS ******************
"""


@app.route('/api/events/', methods=['GET'])
def get_events():
    "Sends back all events"
    content = Event.query.all()
    return jsonify([i.serialize for i in content]), 200


@app.route('/api/events/', methods=['POST'])
def add_event():
    "Inputs new event and saves it in db"
    content = request.get_json(silent=True, force=False)
    if content:
        new_event = Event(gate_id=content.get('gate_id'),
                          ibeacon_uuid=content.get('ibeacon_uuid'),
                          ibeacon_major=content.get('ibeacon_major'),
                          ibeacon_minor=content.get('ibeacon_minor'),
                          in_time=parser.parse(content.get('in_time')),
                          out_time=parser.parse(content.get('out_time')),
                          course=content.get('course'))
        # check if same record exists
        if db.session.query(Event.id).filter((Event.gate_id == new_event.gate_id) &
                                                     (Event.ibeacon_uuid == new_event.ibeacon_uuid) &
                                                     (Event.ibeacon_major == new_event.ibeacon_major) &
                                                     (Event.ibeacon_minor == new_event.ibeacon_minor) &
                                                     (Event.in_time == new_event.in_time) &
                                                     (Event.out_time == new_event.out_time) &
                                                     (Event.course == new_event.course)).count() == 0:
            db.session.add(new_event)
            return "<h1>Ok</h1>", 200
        else:
            return "<h1>Error</h1>", 400
    else:
        return "<h1>Error</h1>", 400


@app.route('/api/events/<int:id>', methods=['PUT'])
def update_event(id):
    "Update event with given id"
    content = request.get_json(silent=True, force=False)
    if content:
        try:
            event = Event.query.filter(Event.id == id).first()
            event.gate_id = content.get('gate_id')
            event.ibeacon_uuid = content.get('ibeacon_uuid')
            event.ibeacon_major = content.get('ibeacon_major')
            event.ibeacon_minor = content.get('ibeacon_minor')
            event.in_time = parser.parse(content.get('in_time'))
            event.out_time = parser.parse(content.get('out_time'))
            event.course = content.get('course')

            db.session.commit()
        except:
            return "<h1>Error</h1>", 404
    else:
        return "<h1>Error</h1>", 400
    return "<h1>Ok</h1>", 200


@app.route('/api/events/<int:id>', methods=['DELETE'])
def delete_event(id):
    "Delete event with given id"
    try:
        Event.query.filter(Event.id == id).delete(synchronize_session='evaluate')
    except:
        return "<h1>Error</h1>", 404
    return "<h1>Ok</h1>", 200


"""
 ****************** TABLES ******************
"""


@app.route('/messages', methods=['GET'])
def messages():
    return render_template("messages.html")


@app.route('/gates/', methods=['GET'])
def gates():
    return render_template("gates.html")


@app.route('/', methods=['GET'])
def events():
    return render_template("events.html")


"""
 ****************** UTILS ******************
"""


@app.route('/api/gates/<int:id>', methods=['DELETE'])
def delete_gate(id):
    "Delete gate with given id"
    try:
        Gate.query.filter(Gate.id == id).delete(synchronize_session='evaluate')
    except:
        return "<h1>Error</h1>", 404
    return "<h1>Ok</h1>", 200


@app.route('/api/collect_items/', methods=['GET'])
def process_overlapps():
    """
    Find overlapping events in Beacon model for all gates from Pair
    If found, calculate course
    Store to Event

    select b1.raspi_serial raspi_one, b1.min_dist dist_one, b2.min_dist dist_two, b1.ibeacon_uuid, b1.ibeacon_major, b1.ibeacon_minor, b1.in_time, b2.out_time
    from beacons b1
    inner join beacons b2
    on b1.ibeacon_uuid = b2.ibeacon_uuid 
    and b1.ibeacon_major = b2.ibeacon_major 
    and b1.ibeacon_minor = b2.ibeacon_minor
    and b1.in_time < b2.in_time
    and b1.out_time > b2.in_time
    where b1.raspi_serial = "000000000f6570bb" or b1.raspi_serial = "00000000f56eacba"
    """
    try:
        gates = Gate.query.all()  # List of all available gates
        for gate in gates:
            # alias, SQLAlchemy cannot join table to itself
            b1 = aliased(Beacon)
            b2 = aliased(Beacon)

            query = db.session.query(b1.raspi_serial.label('raspi_one'),
                                     b1.min_dist.label('dist_one'),
                                     b2.min_dist.label('dist_two'),
                                     b1.ibeacon_uuid,
                                     b1.ibeacon_major,
                                     b1.ibeacon_minor,
                                     b1.in_time,
                                     b2.out_time,
                                     b1.min_time.label('time_one'),
                                     b2.min_time.label('time_two'))
            # sub_query filters records for current gate
            query = query.filter((b1.raspi_serial == gate.raspi_serial_left) |
                                 (b1.raspi_serial == gate.raspi_serial_right))
            # main query, seek for overlapping time intervals for each i-beacon
            query = query.join(b2, (b1.in_time < b2.in_time) &
                               (b1.out_time > b2.in_time) &
                               (b1.ibeacon_uuid == b2.ibeacon_uuid) &
                               (b1.ibeacon_major == b2.ibeacon_major) &
                               (b1.ibeacon_minor == b2.ibeacon_minor))
            records = query.all()

            for record in records:
                # Find left and right side's distance
                if record.raspi_one in db.session.query(Gate.raspi_serial_left).all()[0]:
                    dist_left = record.dist_one
                    time_left = record.time_one
                    dist_right = record.dist_two
                    time_right = record.time_two
                else:
                    dist_right = record.dist_one
                    time_right = record.time_one
                    dist_left = record.dist_two
                    time_left = record.time_two

                # Find course
                if dist_left > gate.distance or dist_right > gate.distance:
                    course = 'wide'
                elif dist_left <= dist_right // 2:
                    course = 'left'
                elif dist_right <= dist_left // 2:
                    course = 'right'
                else:
                    course = 'center'

                new_event = Event(gate_id=gate.id,
                                  ibeacon_uuid=record.ibeacon_uuid,
                                  ibeacon_major=record.ibeacon_major,
                                  ibeacon_minor=record.ibeacon_minor,
                                  in_time=record.in_time,
                                  out_time=record.out_time,
                                  min_time_left = time_left,
                                  min_time_right = time_right,
                                  course=course)
                if db.session.query(Event.id).filter((Event.gate_id == new_event.gate_id) &
                                                             (Event.ibeacon_uuid == new_event.ibeacon_uuid) &
                                                             (Event.ibeacon_major == new_event.ibeacon_major) &
                                                             (Event.ibeacon_minor == new_event.ibeacon_minor) &
                                                             (Event.in_time == new_event.in_time) &
                                                             (Event.out_time == new_event.out_time) &
                                                             (Event.min_time_left == new_event.min_time_left) &
                                                             (Event.min_time_right == new_event.min_time_right) &
                                                             (Event.course == new_event.course)).count() == 0:
                    db.session.add(new_event)

    except:
        return "<h1>Error</h1>", 400
    return "<h1>Ok</h1>", 200


@app.errorhandler(404)
def page_not_found(e):
    "404 error handler"
    return "<h1>Error 404</h1>", 404


if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=80)
