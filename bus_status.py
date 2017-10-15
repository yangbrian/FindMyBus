import logging

from random import randint
from flask import Flask
from flask_dynamo import Dynamo
from flask_ask import Ask, statement, question, session, context
from geopy.geocoders import Nominatim
from Stop import Stop

import requests

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

    # msg = "Your bus is {} {}".format(borough, num)
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

    api_KEY = "a7274011-3c23-4fd2-9641-dcbe0d873f47"
    lat = str(latitude)
    lon = str(longitude)
    URL = "http://bustime.mta.info/api/where/stops-for-location.json?key="+api_KEY+"&lat="+lat+"&lon="+lon+"&radius=321.869"
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


if __name__ == '__main__':
    app.run(debug=True)
