import os
import sys
import json
import random
import uuid
import threading
import requests
from flask import Flask, request

app = Flask(__name__)


statements={
    "instructions":[
        "Let's start! Send me the URL to a paywalled article. I'm still new to this, so if something goes wrong type 'error'.",
        "Hey! Give me a paywalled-article URL and I'll try and get you an Open Access version! ",
        "Hi there! Go ahead and send me a paywalled article URL. (top tip: use the share to menu on your phone to send me links really easily)",
        "Hello! The first step is to send me a URL to a paywalled article. Pro tip, type 'error' if something odd happens.",
        "oh hi, need a paper? Send me a link and I'll try and track down a free version. (top tip: use the share to menu on your phone to send me links really easily)",
        "Looking for Open Access? Send me a paywall URL and I'll try to find you an available version. " # commas not on the last line
    ],
    "loading":[
        "Hmmm, let's take a look... ",
        "One second! Here it comes... ",
        "Wait just a sec - I'm searching... ",
        "Please wait while I work on that for you. ",
        "brb, just going to take a look for you. ",
        "Let's take a look. Please wait! "
    ],

    # leave a space at the end so the text doesn't screw up the link.
    "success":[
        "Great news! We found something! (If it's wrong, type 'error'.) ",
        "Looks like we found something! (If this isn't what you're looking for, type 'error'.) ",
        "Tada! (If this is wrong, type 'error.') ",
        "Here's what I found (if I messed up, type 'error'): ",
        "Is this what you were looking for? (If not, type 'error'.) "
    ],

    # suggest we have a separate "ifnotright":[ message show up automatically 5 seconds after the success message
    # "If this isn't what you're looking for, type 'error'."
    # ],


    # request link needs to be at the end. Make clear what a request is in any response.
    "support":[
        "It's not available yet, but someone has asked the author. Add your support: https://dev.openaccessbutton.org/request/",
        "We've got a request, which you can add your support to: https://dev.openaccessbutton.org/request/",
        "Someone's already asked the author for that: https://dev.openaccessbutton.org/request/",
        "It's been requested by another researcher - you can add your support! https://dev.openaccessbutton.org/request/",
        "Someone else wants that article too! Add your support here: https://dev.openaccessbutton.org/request/"
    ],

    # same as above
    "notoa":[
        "Sad times, we can't find anything. Why not ask the author to make a copy available? https://dev.openaccessbutton.org?plugin=chatbot&url=",
        "Bad luck! Nothing's available. Make a request directly to the author at https://dev.api.cottagelabs.com/service/oab?plugin=chatbot&url=",
        "It hasn't been made Open yet, but you can help! Ask the author here: https://dev.openaccessbutton.org?plugin=chatbot&url=",
        "OH no, it's paywalled! Help make it Open Access by asking the author directly - https://dev.openaccessbutton.org?plugin=chatbot&url=",
        "Ugh, it's not Open Access yet. Ask the author to make a copy available - https://dev.openaccessbutton.org?plugin=chatbot&url="
    ],

    # no link returned here. Could return a bug link.
    "notarticle":[
        "Looks like I need a bit more training. Let us know what happened - https://openaccessbutton.org/feedback#bug ",
        "Sorry, I guess I have a bug. Fill out https://openaccessbutton.org/feedback#bug plz. ",
        "Something didn't work. File a bug report at https://openaccessbutton.org/feedback#bug ",
        "Yikes, that didn't go well. Give us some information about your problem at https://openaccessbutton.org/feedback#bug ",
        "Oh noes! Send us a bug report at https://openaccessbutton.org/feedback#bug "
    ]
}

@app.route('/', methods=['GET'])
def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


@app.route('/', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    data = request.get_json()
    log(data)  # you may not want to log every incoming message in production, but it's good for testing

    if data["object"] == "page":

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:

                if messaging_event.get("message"):  # someone sent us a message

                    sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    message_text = messaging_event["message"]["text"]  # the message's text

                    if "http" in message_text:
                        thr = threading.Thread(target=query_api, args=("http"+message_text.split("http")[1].split(" ")[0],sender_id), kwargs={})
                        thr.start()
                    elif "error" in message_text:
                        send_message(sender_id, random.choice(statements["notarticle"])) # if the user says "error", send an error note.

                    else:
                        send_message(sender_id, random.choice(statements["instructions"])) # if not a URL, send along instructions

                if messaging_event.get("delivery"):  # delivery confirmation
                    pass

                if messaging_event.get("optin"):  # optin confirmation
                    pass

                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass

    return "ok", 200


def query_api(URL,sender_id):
    send_message(sender_id, random.choice(statements["loading"])) # this message responds immediately to let them know we're working
    RES=requests.get("https://dev.api.cottagelabs.com/service/oab/find/?plugin=chatbot&url="+URL) # send the URL off to the OAB API
    try:
        if len(RES.json()["data"]["availability"])>0: # check is the api returns a successful results
            send_message(sender_id, random.choice(statements["success"])+RES.json()["data"]["availability"][0]["url"]) # if the API is successful, return the URL. e.g http://stm.sciencemag.org/content/6/234/234ra59
        elif len(RES.json()["data"]["requests"])>0: # check if we have a request e.g http://immunology.sciencemag.org/content/2/14/eaan5393
            send_message(sender_id, random.choice(statements["support"])+RES.json()["data"]["requests"][0]["_id"]) # if there are no requests or oa versions, send a sad message.
        else:
            send_message(sender_id, random.choice(statements["notoa"])+URL) # if the above isn't true, send a sad message. You can use this URL https://link.springer.com/article/10.1007%2FBF00326615?LI=true but who knows... someone might make a request or OA for it one day!
    except:
        send_message(sender_id, random.choice(statements["notarticle"])) # if the api returns nothing, drop the user an error note


def send_message(recipient_id, message_text):


    myuuid = uuid.uuid4().hex

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text + " debug: " + myuuid))

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text + " debug: " + myuuid
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)


def log(message):  # simple wrapper for logging to stdout on heroku
    print str(message)
    sys.stdout.flush()


if __name__ == '__main__':
    app.run(debug=True)
