# -*- coding: utf-8 -*-

"""
Simple server
Takes i-beacon read data with POST method
Return summary data with GET
"""

from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import os
import json
from dateutil import parser


basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir,'data.sqlite3')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Beacon(db.Model):
    """
    I-beacon data model
    """
    __tablename__ = 'beacons'

    id = db.Column(db.Integer, primary_key=True)
    raspi_serial = db.Column(db.String(14), index=True)
    ibeacon_uuid = db.Column(db.String(32))
    ibeacon_major = db.Column(db.Integer, index=True)
    ibeacon_minor = db.Column(db.Integer, index=True)
    in_time = db.Column(db.DateTime, index=True)
    out_time = db.Column(db.DateTime, index=True)
    min_dist = db.Column(db.Integer)

    @property
    def serialize(self):
       """Return object data in easily serializeable format"""
       return {
           'id': self.id,
           'raspi_serial': self.raspi_serial,
           'ibeacon_uuid': self.ibeacon_uuid,
           'ibeacon_major': self.ibeacon_major,
           'ibeacon_minor': self.ibeacon_minor,
           'in_time': self.in_time.isoformat(),
           'out_time': self.out_time.isoformat(),
           'min_dist': self.min_dist
       }


@app.errorhandler(404)
def page_not_found(e):
    """
    404 error handler
    """
    return "<h1>Error 404</h1>", 404


@app.route('/api/add_message/', methods=['GET', 'POST'])
def add_message():
    """
    Inputs new messages and saves it in db
    """
    content = request.get_json(silent=True, force=False)
    if content:
        new_beacon = Beacon(raspi_serial = content.get('raspi_serial'),
                            ibeacon_uuid = content.get('ibeacon_uuid'),
                            ibeacon_major=content.get('ibeacon_major'),
                            ibeacon_minor=content.get('ibeacon_minor'),
                            in_time = parser.parse(content.get('in_time')),
                            out_time = parser.parse(content.get('out_time')),
                            min_dist = content.get('min_dist'),)
        db.session.add(new_beacon)
        return "<h1>Ok</h1>", 200
    else:
        return "<h1>Error</h1>", 400


@app.route('/api/get_messages/', methods=['GET'])
def get_messages():
    """
    Sends back messages for time between start and end
    """
    try:
        start = parser.parse(request.args.get('start'))
        end = parser.parse(request.args.get('end'))
    except:
        return "<h1>Error</h1>", 400

    content = Beacon.query.filter((Beacon.out_time >= start) & (Beacon.in_time <= end)).all()
    return jsonify([i.serialize for i in content]), 200


@app.route('/api/get_messages/all/', methods=['GET'])
def get_all_messages():
    """
    Sends back all messages
    """
    content = Beacon.query.all()
    return jsonify([i.serialize for i in content]), 200


@app.route('/api/delete_message/<int:id>', methods=['DELETE'])
def delete_message(id):
    """
    Delete message with given id
    """
    try:
        Beacon.query.filter(Beacon.id==id).delete(synchronize_session='evaluate')
    except:
        return "<h1>Error</h1>", 400
    return "<h1>Ok</h1>", 200

@app.route('/')
def index():
    content = Beacon.query.all()
    data = json.dumps([i.serialize for i in content])
    return render_template("table.html", data=data)


if __name__== "__main__":
    app.run(debug=False, host='0.0.0.0', port=80)
