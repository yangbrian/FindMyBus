import logging

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

    if 'Item' in response:
        item = response['Item']
        return statement("Your favorite bus is {}".format(item['bus_route']))
    else:
        return question("Welcome! You do not have a bus route and stop setup yet. Would you like to do so now?")

@ask.intent("YesIntent")
def yes_proceed():

    yes_msg = "Great! What's your preferred bus route?"

    return question(yes_msg)

@ask.intent("NoIntent")
def no_proceed():

    return question("Okay how about now?")

@ask.intent("AnswerIntent", convert={'borough': 'string', 'num': 'int'})
def answer(borough, num):

    """
    dynamo.tables['buses'].put_item(Item={
        'user_id': session.user.userId,
        'bus_route': "{} {}".format(borough, num)
    })
    """

    msg = "Your bus is {} {}. ".format(borough, num)

    # HARDCODED TEST
    #stop_id = 551744
    #return statement(get_eta_message('Q65', stop_id))

    msg = "Your bus is {} {}. ".format(borough, num)
    msg += display_stops(find_stops())
    print(msg)
    return statement(msg)

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
    print((geo_location.latitude, geo_location.longitude))

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
        stopStr+=str(idx)+' '+stop.audioName+'. \n'
    
    return stopStr


def get_list_of_stops(stops):
    stop_list = []
    for stop in stops['data']['stops']:
        name = stop['name']
        code = stop['code']
        buses = []
        for routes in stop['routes']:
            buses.append(routes['shortName'])
        stop = Stop(name,code,buses)
        stop_list.append(stop)
    return stop_list[:5]

def get_eta_message(bus_route, stop_id):
    """Get number of minutes until next bus arrival
    Returns -1 if no bus available (or if bus doesn't even stop here)
    
    Args:
    stop_id -- GTFS bus ID code (6 digits)
    bus_route -- bus route (like Q58 or M96) 
    """

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

        final_message += "It is {}.".format(distance)
    else:
        final_message += "The {} is {}".format(bus_route, distance)

    return final_message

if __name__ == '__main__':
    app.run(debug=True)
