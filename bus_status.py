import logging
import re
import json
from random import randint
from flask import Flask
from flask_dynamo import Dynamo
from flask_ask import Ask, statement, question, session, context
from geopy.geocoders import Nominatim
from Stop import Stop
import iso8601
import datetime
import time

import math
import requests

MTA_API_KEY = "a7274011-3c23-4fd2-9641-dcbe0d873f47"

app = Flask(__name__)
ask = Ask(app, "/")
logging.getLogger("flask_ask").setLevel(logging.DEBUG)

# DynamoDB config
app.config['DYNAMO_TABLES'] = [
    {
        'TableName': 'buses',
        'KeySchema': [dict(AttributeName='user_id', KeyType='HASH')], 
        'AttributeDefinitions': [dict(AttributeName='user_id', AttributeType='S')],
        'ProvisionedThroughput': dict(ReadCapacityUnits=5, WriteCapacityUnits=5)
    }
]
dynamo = Dynamo(app)

# create tables if doesn't exist
with app.app_context():
    dynamo.create_all()

@ask.launch
def welcome():

    # check if user already has a saved bus
    response = dynamo.tables['buses'].get_item(Key={'user_id': session.user.userId })

    if 'Item' in response and 'bus_stop' in response['Item']:
        item = response['Item']

        session.attributes['bus_route'] = item['bus_route']
        session.attributes['bus_stop'] = item['bus_stop']
        session.attributes['stop_code'] = item['stop_code']

        return question("Welcome to Find My Bus!")
    else:
        return question("Welcome to Find My Bus! You do not have a bus route and stop setup yet. Would you like to do so now?")

@ask.intent("YesIntent")
def yes_proceed():

    yes_msg = "Great! What's your preferred bus route?"

    return question(yes_msg)

@ask.intent("PickIntent", convert={'num':'int'})
def pick_number(num):
    number = int(num)
    if session.attributes['nearbyStops']:
        nearby_stops = json.loads(session.attributes['nearbyStops'])
        selected_stop = nearby_stops[number-1]
        msg = "Your default bus stop is {}. ".format(selected_stop['audioName'])

        # Persist info into database
        dynamo.tables['buses'].put_item(Item={
            'user_id': session.user.userId,
            'bus_route': session.attributes['bus_route'],
            'bus_stop': selected_stop['audioName'],
            'stop_code': selected_stop['code']
        })

        session.attributes['bus_stop'] = selected_stop['audioName']
        session.attributes['stop_code'] = selected_stop['code']

        msg += "You have completed the setup. You may now ask Where is the bus upon starting this skill. Try it now!"

    else:
        msg = "Please allow Alexa to get your location in order to choose a bus stop"

    return statement(msg)

@ask.intent("NoIntent")
def no_proceed():

    return statement('Okay. Good day.')

@ask.intent("BusTimeIntent")
def bus_time_intent():

    # make sure session objects are ready
    if 'bus_route' not in session.attributes or 'bus_stop' not in session.attributes or 'stop_code' not in session.attributes:
        return question('You do not have your preferred route and stop set yet. Would you like to set them now?')

    bus_route = session.attributes['bus_route']
    bus_stop = session.attributes['bus_stop']
    stop_code = session.attributes['stop_code']

    return statement(get_eta_message(bus_route, stop_code, bus_stop))

@ask.intent("AnswerIntent", convert={'borough': 'string', 'num': 'int'})
def answer(borough, num):

    complete = borough+ str(num)

    groups = re.search(r'([A-z]).*\..*?([0-9]+)$', complete)
    session.attributes['bus_route'] = groups.group(1) + ' ' + groups.group(2)

    msg = "<speak>Your bus is {} {}. ".format(borough, num)

    stops = find_stops()

    session.attributes['nearbyStops'] = json.dumps(stops, default=obj_dict)

    msg += display_stops(stops)+'</speak>'
    print(msg)
    return question(msg)

def obj_dict(obj):
    return obj.__dict__

def mapStops(stops):
    nearby_stops = {}
    for idx,stop in enumerate(stops):
        nearby_stops[idx+1] = stop
    return nearby_stops

        
def filterStops(stops):
    filteredStops = []
    bus = session.attributes['bus_route'].replace(' ','')

    for stop in stops:
        if bus.upper() in map(str.upper, stop.buses):
            filteredStops.append(stop)

    return filteredStops

def getLocation():
    deviceId = context.System.device.deviceId
    URL =  "https://api.amazonalexa.com/v1/devices/{}/settings" \
           "/address".format(deviceId)
    TOKEN =  context.System.user.permissions.consentToken
    HEADER = {'Accept': 'application/json',
             'Authorization': 'Bearer {}'.format(TOKEN)}
    r = requests.get(URL, headers=HEADER)
    if r.status_code == 200:
        resp = r.json()
        return resp

def find_stops():
    location = getLocation()
    geopy_loc = location['addressLine1'] + " "+ location['stateOrRegion']
    geopy_loc = geopy_loc.replace(' E ', ' ')
    geopy_loc = geopy_loc.replace(' W ', ' ')

    geolocator = Nominatim()
    geo_location = geolocator.geocode(geopy_loc)


    return get_nearby_stops(geo_location.latitude, geo_location.longitude)

def get_nearby_stops(latitude, longitude):

    lat = str(latitude)
    lon = str(longitude)
    URL = "http://bustime.mta.info/api/where/stops-for-location.json?key="+MTA_API_KEY+"&lat="+lat+"&lon="+lon+"&radius=321.869"
    r = requests.get(URL)
    if r.status_code == 200:
        return get_list_of_stops(r.json())

def display_stops(stops):
    stopStr = 'The available stops are '
    for idx,stop in enumerate(stops):
        stopStr+= '<break time="0.5s" />Choose, '+ str(idx+1)+' for <break time="0.5s"/> '+stop.audioName+'. \n'
    
    return stopStr


def get_list_of_stops(stops):
    stop_list = []
    for stop in stops['data']['stops']:
        name = stop['name']
        code = stop['code']
        buses = []
        for routes in stop['routes']:
            buses.append(routes['shortName'])
            print(routes['shortName'])
        stop = Stop(name,code,buses)
        stop_list.append(stop)
    return filterStops(stop_list)[:5]

def get_eta_message(bus_route, stop_id, bus_stop):
    """Get number of minutes until next bus arrival
    Returns -1 if no bus available (or if bus doesn't even stop here)
    
    Args:
    stop_id -- GTFS bus ID code (6 digits)
    bus_route -- bus route (like Q58 or M96) 
    bus_stop -- bus stop name
    """

    # fix bus formatting
    bus_route = bus_route.upper().replace(' ', '')

    # MTA buses are either MTA NYCT_Q50 or MTABC_Q50
    # Let's try them both

    r = requests.get('http://bustime.mta.info/api/siri/stop-monitoring.json', 
            params = {
                'key': MTA_API_KEY,
                'OperatorRef': 'MTA',
                'MonitoringRef': stop_id,
                'LineRef': 'MTA NYCT_{}'.format(bus_route)
            })

    r = r.json()

    # check for errors
    if 'ErrorCondition' in r['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0]:
        r = requests.get('http://bustime.mta.info/api/siri/stop-monitoring.json', 
                params = {
                    'key': MTA_API_KEY,
                    'OperatorRef': 'MTA',
                    'MonitoringRef': stop_id,
                    'LineRef': 'MTABC_{}'.format(bus_route)
                })

        r = r.json()

    # still bad route?
    if 'ErrorCondition' in r['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0]:
        return "No such route"


    arrivals = r['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0]['MonitoredStopVisit']

    if len(arrivals) == 0:
        return "No known {} arrivals expected.".format(bus_route)

    arrival = arrivals[0]['MonitoredVehicleJourney']['MonitoredCall']

    final_message = ''

    # distance if time is unavailable
    distance = arrival['Extensions']['Distances']['PresentableDistance']

    if 'ExpectedArrivalTime' in arrival:
        iso_time = arrival['ExpectedArrivalTime']

        # calculated ETA
        arrival_time = time.mktime(iso8601.parse_date(iso_time).timetuple())
        current_time = time.mktime(datetime.datetime.now().timetuple())

        eta = math.floor((arrival_time - current_time) / 60 * 100) / 100
        final_message += "The {} will arrive in {} minutes. ".format(bus_route, eta)

        final_message += "It is {} from {}.".format(distance, bus_stop)
    else:
        final_message += "The {} is {} from {}".format(bus_route, distance, bus_stop)

    return final_message

if __name__ == '__main__':
    app.run(debug=True)
