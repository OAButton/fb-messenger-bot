import os
import sys
import json
import random

import requests
from flask import Flask, request

app = Flask(__name__)


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

    statements={
        instructions:[
            "I'm statement one",
            "Hey! Give me an article URL and I'll try and get you an Open Access version!",
            "I'm statement two"  # commas not on the last line
        ],
        loading:[
            "One second! Here it comes..."
        ],
        success:[
            "I am a statement"
        ],
        request:[],
        sad:[],
        fail:[]
    }

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
                        URL="http"+message_text.split("http")[1].split(" ")[0] # extract a URL
                        send_message(sender_id, "One second! Here it comes...") # this message responds immediately to let them know we're working
                        RES=requests.get("https://api.openaccessbutton.org/find/?from=fbapp&url="+URL) # send the URL off to the OAB API
                        try:
                            if len(RES.json()["data"]["availability"])>0: # check is the api returns a successful results
                                send_message(sender_id, RES.json()["data"]["availability"][0]["url"]) # if the API is successful, return the URL. e.g http://stm.sciencemag.org/content/6/234/234ra59
                            elif len(RES.json()["data"]["requests"])>0: # check if we have a request e.g http://immunology.sciencemag.org/content/2/14/eaan5393
                                send_message(sender_id, "We've got a request https://openaccessbutton.org/request/"+RES.json()["data"]["requests"][0]["_id"]) # if there are no requests or oa versions, send a sad message.
                            else:
                                send_message(sender_id, "Bad luck, try again next time. Maybe try and make a request at https://openaccessbutton.org?url="+URL) # if the above isn't true, send a sad message. You can use this URL https://link.springer.com/article/10.1007%2FBF00326615?LI=true but who knows... someone might make a request or OA for it one day!
                        except:
                            send_message(sender_id, "Sorry, I f*cked up. Drop hello@openaccessbutton.org an email plz.") # if the api returns nothing, drop the user an error note
                    else:
                        send_message(sender_id, random.choice(statements["instructions"])) # if not a URL, send along instructions

                if messaging_event.get("delivery"):  # delivery confirmation
                    pass

                if messaging_event.get("optin"):  # optin confirmation
                    pass

                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass

    return "ok", 200


def send_message(recipient_id, message_text):

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

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
            "text": message_text
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
