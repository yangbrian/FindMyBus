import logging

from random import randint
from flask import Flask, render_template
from flask_ask import Ask, statement, question, session
from flask_dynamo import Dynamo

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

    welcome_msg = render_template('welcome')

    # check if user already has a saved bus
    response = dynamo.tables['buses'].get_item(Key={'user_id': session.user.userId })

    if 'Item' in response:
        item = response['Item']
        return statement("Your favorite bus is {}".format(item['bus_route']))
    else:
        return question("Welcome! You do not have a bus route and stop setup yet. Would you like to do so now?")

@ask.intent("YesIntent")
def yes_proceed():

    yes_msg = render_template('proceed')
    return question(yes_msg)

@ask.intent("NoIntent")
def no_proceed():

    return question("Okay how about now?")

@ask.intent("AnswerIntent", convert={'borough': 'string', 'num': 'int'})
def answer(borough, num):

    dynamo.tables['buses'].put_item(Item={
        'user_id': session.user.userId,
        'bus_route': "{} {}".format(borough, num)
    })

    msg = "Your bus is {} {}".format(borough, num)

    return statement(msg)

if __name__ == '__main__':
    app.run(debug=True)
