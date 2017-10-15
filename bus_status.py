import logging

from random import randint
from flask import Flask, render_template
from flask_ask import Ask, statement, question, session, context
from geopy.geocoders import Nominatim
from Stop import Stop

import requests

app = Flask(__name__)
ask = Ask(app, "/")
logging.getLogger("flask_ask").setLevel(logging.DEBUG)

@ask.launch
def new_game():

    welcome_msg = render_template('welcome')
    return question(welcome_msg)

@ask.intent("YesIntent")
def yes_proceed():
    
    yes_msg = render_template('proceed')

    return question(yes_msg)

@ask.intent("NoIntent")
def no_proceed():

    repeat_msg = render_template('repeat')
    return question(repeat_msg)

@ask.intent("AnswerIntent", convert={'borough': 'string', 'num': 'int'})
def answer(borough, num):
    # msg = "Your bus is {} {}".format(borough, num)
    msg = display_stops(find_stops())
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
