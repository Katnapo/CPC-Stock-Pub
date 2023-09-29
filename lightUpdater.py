import re
import time
from APITools import ShopifyApiHelper
import APITools
import databaseHandler
from datetime import date
import uuid
from constants import Constants

# Initial built code.
def mainUpdater():


    shopifyApiHelper = ShopifyApiHelper()
    sessionId = str(uuid.uuid4())

    def getAllShopifySkusWithStockLevelId():

        databaseHandler.setLogsToDatabase("[UP][INFO]LightUpdater",
                                      "The light updater has successfully been initiated. Session ID is: " + sessionId)
        a = 0
        mainList = []
        limiter = False
        # WARNING!!!!! IF USING THIS CODE NOT ON WAL, PLEASE CHANGE THE "SINCE_ID" TO THE OLDEST PRODUCT CURRENTLY
        # IN ACTIVE.
        x = (shopifyApiHelper.constructShopifyGetRequest("products.json",
                                                [["limit", 250], ["status", "active"], ["order", "created_at+asc"]])).json()

        for item in x["products"]:
            for variant in item["variants"]:
                a = a + 1
                sku = (variant["sku"]).upper()
                if sku[-2:] == "-D" or sku[-2:] == "-d":
                    continue
                mainList.append([variant["inventory_item_id"], sku])

        while limiter == False:

            try:
                lastid = x["products"][-1]["id"]

                x = (shopifyApiHelper.constructShopifyGetRequest("products.json", [["limit", 250],["status", "active"],["since_id", str(lastid)]])).json()
                for item in x["products"]:
                    for variant in item["variants"]:
                        sku = (variant["sku"]).upper()
                        if sku[-2:] == "-D" or sku[-2:] == "-d":
                            continue
                        mainList.append([variant["inventory_item_id"], variant["sku"]])

            except Exception as e:
                limiter = True

        databaseHandler.setLogsToDatabase("[UP][INFO]LightUpdater",
                                      "The light updater collected all the items and escaped the loop. Session ID is: " + sessionId)

        return mainList

    def getBcStockLevels(sku):

        level = (APITools.bcGetRequest(APITools.urlFilterByCpCodeSKU("URL_REDACTED", sku))).json()["value"]
        try:
            return level[0]["currentStockAvaliable"]
        except Exception as e:
            databaseHandler.setLogsToDatabase("[UP][ERROR]LightUpdater",
                                          "The light updater ran into a problem getting BC stock levels. Data was: " + str(sku) + " sku, " + str(level) + " response and error of " + str(e) + ". Session ID is: " + sessionId)
            return None

    def updateShopifyStockLevel(value, itemId):

        headers = APITools.constructHTTPComponent("H", [["Content-Type", "application/json"]])
        #body = apiTools.constructHTTPComponent("B", [["location_id", Constants.SHOPIFY_LOC], ["inventory_item_id",itemId], ["available", value]])
        body = APITools.constructHTTPComponent("B", [["location_id", Constants.SHOPIFY_LOC], ["inventory_item_id",itemId], ["available", value]])
        a = shopifyApiHelper.constructShopifyPostRequest("inventory_levels/set.json", headers, body)

        return a

    def getShopifyLevels(shopifyInvId):

        url = "inventory_levels.json?inventory_item_ids=" + str(shopifyInvId)
        a = (shopifyApiHelper.constructShopifyGetRequest(url)).json()
        if len(re.findall("inventory_levels", str(a))) != 0:
            return int(a["inventory_levels"][0]["available"])

        else:
            raise Exception("Faliure to get stock level check. Check iterator")


    def main():

        productArray = getAllShopifySkusWithStockLevelId()
        today = (date.today()).strftime("%Y-%m-%d")
        databaseHandler.setLogsToDatabase("[UP][INFO]LightUpdater",
                                      "The light updater made it to phase 2. It is now going to update the stock levels. It is going to update " + str(len(productArray)) + " items. The date is " + str(today) + ". Session ID is: " + sessionId)
        updates = 0

        for item in productArray:
            try:
                level = getBcStockLevels((item[1]).upper())
                spVal = getShopifyLevels(item[0])
                print(str(level) + ":" + str(spVal))

                if level is None:
                    continue

                if spVal == level:
                    continue

                a = updateShopifyStockLevel(level, item[0])
                databaseHandler.setLogsToDatabase("[UP][INFO]LightUpdater",
                                              "Updating stock. Levels are " + str(level) + ":" + str(spVal) + " with response " + str(a.json()) + ". Session ID is: " + sessionId)

                if len(re.findall(str(today), str(a.json()))) == 1:
                    updates = updates + 1

            except Exception as e:
                databaseHandler.setLogsToDatabase("[UP][ERROR]LightUpdater",
                                              "Exception occurred for sku " + str(item[1]) + " with error " + str(e) + ". Session ID is: " + sessionId)
                continue

        databaseHandler.setLogsToDatabase("[UP][INFO]LightUpdater",
                                      "Light Updater phase 2 fin. Total amount of updates made were " + str(updates) +  ". Session ID is: " + sessionId)

    
    main()
