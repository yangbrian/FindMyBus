## Where's the Bus?

MTA BusTime implementation for the Amazon Echo and other Alexa enabled devices.

Start skill: ask find the bus

Intents:
YesIntent - respond yes to are you ready
NoIntent - respond no to are you ready
AnswerIntent - provide favorite bus like Q44

### Setup
Make sure you have virtualenv for Python setup.

In your project directory, run the following:

```
pip3 install virtualenv
virtualenv -p python3 hackny
. hackny/bin/activate
```

Now, any packages you run will install locally to your project directory only.

```
pip install flask-ask zappa requests awscli
```

### Files

bus\_status.py contains all the code. 
templates.yaml contains all strings. Access via render\_template(NAME). See existing examples.

### Deploy to server (not needed when testing locally)

```
zappa update dev
```

Go to https://developer.amazon.com/edw/home.html#/skill/amzn1.ask.skill.d78023b2-f10c-4f8e-8fe9-bdacab8c61da/en_US/configuration and set the HTTPS URL to the URL you see on zappa.

### Run locally

```
python bus_status.py
```

Then in another terminal/tab, run:

```
ngrok http 5000
```

Go to https://developer.amazon.com/edw/home.html#/skill/amzn1.ask.skill.d78023b2-f10c-4f8e-8fe9-bdacab8c61da/en_US/configuration and change the endpoint to the HTTPS URL you see on ngrok.


