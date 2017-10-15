import logging

from random import randint
from flask import Flask, render_template
from flask_ask import Ask, statement, question, session

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

    msg = "Your bus is {} {}".format(borough, num)
    return statement(msg)

if __name__ == '__main__':
    app.run(debug=True)
