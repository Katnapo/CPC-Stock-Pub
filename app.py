from flask import Flask, request, Response, render_template, make_response
import json
import atexit
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import databaseHandler
from APITools import ShopifyApiHelper
from Updater import InventoryLevelIDPirate, UpdateProcessor
import lightUpdater
import Webhook
from constants import Constants
# ((               ))
#  )) Flask Server v1.1 FOR SYNC ((
# ((               ))
#   ---------------

## NOTE, THIS VERSION OF THE Flask Server IS SIMPLIFIED FOR PRODUCTION AND TUNED FOR SYNCING PRODUCT STOCK LEVELS ##
# V 1.1 - 12/07/2022 - Cleaned up webhook processing, made database handling and api handling into singleton processes.

databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "The server was restarted. Current system time is: " + str(datetime.now()))
localNotifEndpoint = "default"
currentHook = None


# Generate the api tools and database tools helper objects, for sending api requests and accessing the database
shopifyApiObject = ShopifyApiHelper()
databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "The server was restarted. Current system time is: " + str(datetime.now()))

# Create the updater classes for the OOP updaters - for webhook and non webhook (heavy updater)
stockLevelSyncProcessorHeavy = UpdateProcessor(shopifyApiObject, Constants.SHOPIFY_LOC)
stockLevelSyncProcessorHook = UpdateProcessor(shopifyApiObject, Constants.SHOPIFY_LOC)
invPirate = InventoryLevelIDPirate(shopifyApiObject, Constants.SHOPIFY_LOC)
webhookFactory = Webhook.WebhookFactory()

# Functions for syncing stock levels. Explained.
#
# Light Updater
#
# The light updater was built first as a quick solution that REDACTED needed. It still works and is not built on
# OOP - I consider it unreliable but this still works as a 'Dirty' piece of code to use in testing. It's
# what REDACTED has run on for a long time. It also works without the database table, so if any new items
# are added and the relationship table is not updated, it wont matter. It requires, however, a reference item
# in shopify's active category, and for this item to be the oldest item possible (unlisted, of course).
# This is neccesary as I haven't found a way around using the shopify API giving me items since a certain date,
# meaning without this item it is not guaranteed every item will be fetched.
#
# Heavy Updater
#
# The heavy updater is reliant on the UpdateProcessor class and the objects it spawns. It also relies on the
# table sku_shopify_relation to be populated with the latest information. In comparison to the light updater,
# it is bulkier making it "heavier" but this comes with additional error trapping and no reliance on
# a reference item.
#
# To decrease the chances of there being a collision between a webhook update and a heavy update, both updating
# methodologies are using two separate object instances

def stockLevelHeavyUpdater():

    databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "The heavy updater was started. UUID session subscription was: "
                                  + localNotifEndpoint)
    stockLevelSyncProcessorHeavy.heavyUpdate()
    databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "The heavy updater finished. UUID session subscription was: "
                                  + localNotifEndpoint)

def stockLevelLightUpdater():

    # Warning! Light updater does not log to database... only use it if you can see flask's output or you know what you
    # are doing.

    databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "The light updater was started. UUID session subscription was: "
                                  + localNotifEndpoint)
    lightUpdater.mainUpdater()
    databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "The light updater finished. UUID session subscription was: "
                                  + localNotifEndpoint)

def patcher():

    # The PATCH doesn't currently validate the shared secret as it's not doing anything with what is returned.
    # This is however implemented for future use
    try:
        if currentHook == None:
            databaseHandler.setLogsToDatabase("[UP][WARN]FlaskUpdater", "Current hook is None. Skipping patch.")
            return None
        result = currentHook.patchSubscription()
        databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "The PATCH was sent. UUID session subscription was: "
                                  + localNotifEndpoint + " with result of " + str(result))
    except Exception as e:
        databaseHandler.setLogsToDatabase("[UP][ERROR]FlaskUpdater", "The PATCH was unsuccessful. UUID session subscription was: "
                                  + localNotifEndpoint + " Error: " + str(e))

# Server setup is triggered 10 seconds after the server starts. It wipes the log table and generates a webhook subscription
def serverSetup(truncateLogs=False):

    global currentHook
    global localNotifEndpoint

    try:
        if truncateLogs:
            databaseHandler.logTableTruncater()
        currentHook = webhookFactory.getSubscriptionByEventType("itemStockLevels")
        localNotifEndpoint = currentHook.getEndpoint()
        return "Success! Subscription UUID is: " + localNotifEndpoint
    except Exception as e:
        return "Error: " + str(e)


# Scheduler module for scheduling functions to run at certain intervals

scheduler = BackgroundScheduler()
startTime = datetime.now()
setupTriggerDelay = timedelta(seconds=10)
setupTime = startTime + setupTriggerDelay

scheduler.add_job(func=patcher, trigger="interval", hours=4)
scheduler.add_job(func=serverSetup, trigger="date", run_date=setupTime)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


### </1> ###


app = Flask(__name__)


@app.route("/")
def index():
    if currentHook is None:
        return "Hook is currently none. Webhooks not operational."
    return "Index page says hello :) Hope your day is okay ish." + "Current hook id is: " + str(currentHook.getId()) + ", the endpoint is: " + str(currentHook.getEndpoint()) + ",the subscription id is: " + str(currentHook.getSubscriptionId())

@app.route("/retrySerevrSetup")
def getNewKey():
    return serverSetup(False)


@app.route("/hook/<subscription>", methods=['POST', 'GET'])
def respond(subscription):

    # Request is a variable provided by flask for this endpoint. This is then turned into json and unpacked in this segment
    recieved = request.json
    a = json.loads(json.dumps(recieved, indent=4, sort_keys=True))
    skuList = []

    # The code tries to unpack using "value", which would indicate that it contains CP Item numbers
    try:
        for item in a["value"]:
            print(item)

            if currentHook == None:
                databaseHandler.setLogsToDatabase("[UP][WARN]FlaskUpdater", "Current hook is None. Skipping update.")
                break

            if item["subscriptionId"] != str(currentHook.getSubscriptionId()):
                # databaseHandler.setLogsToDatabase("[HK][ERROR]FlaskUpdater",
                #                               "A subscription ID was not matched. The subscription ID was "
                #                               + item["subscriptionId"] + " while the expected subscription ID was " + str(currentHook.getSubscriptionId()) +
                #                               " with a response of " + str(a))
                #
                continue

            # Check for shared secret
            if item["clientState"] != currentHook.getSecret():
                databaseHandler.setLogsToDatabase("[HK][WARN]HookRequest",
                                                   "A post request returned an incorrect shared "
                                                   "secret. Request line contained: " + str(item))
                continue

            skuList.append(((item["resource"]).split("itemStockLevels")[1]).replace(")", "").replace("(", "").replace("'", ""))

    # If the value key cant be found, the code above should fail and it will then be checked for validation token
    except Exception as excp:
        try:
            databaseHandler.setLogsToDatabase("[HK][INFO]FlaskUpdater",
                                          "Data delivered to variable UUID " + subscription + " was not cp item codes. Checking for "
                                                                                      "validation token. Error was: " + str(excp))

            # The validation token is contained in the request's arguments usually, so an attempt is made here to unpack it.
            valtoken = request.args["validationToken"]
            databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater",
                                          "Data delivered to variable UUID " + subscription + " was validation token " + valtoken)
            return make_response(valtoken, 200)

        # If, worryingly, neither data type is found log the incident and move on
        except Exception as excpTwo:
            databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater",
                                          "Data delivered to variable UUID " + subscription + " was neither validation token or cp item codes. Data was "
                                            + str(recieved))
            return (Response(status=200))

    # Send the sku list to update with the webhook updater.
    stockLevelSyncProcessorHook.webhookUpdate(skuList)

    return (Response(status=200))

# Manually trigger the heavy updater, light updater and pirate (The pirate builds the translation table).
@app.route("/heavy")
def hvy():
    stockLevelHeavyUpdater()
    return "Process complete for heavy updater"

@app.route("/light")
def lgt():
    stockLevelLightUpdater()
    return "Process complete for light updater"

@app.route("/pirate")
def invP():
    invPirate.run(True)
    return "Shopify has been plundered of its inventory codes! Yar!"

@app.route("/patch")
def callPatch():
    patcher()
    return "Sent a patch request"


if __name__ == '__main__':
    app.run()

