from datetime import datetime
from datetime import date
import re
import time
import APITools
import databaseHandler

class InventoryItem:

    def __init__(self, sku, shopifyApiHelper, shopifyInventoryId, shopifyLocationId, stockIncreaseFilter=False,
                 debug=True, apiType="Default"):

        self.shopifyApiTools = shopifyApiHelper
        self.sku = sku
        self.stockIncreaseFilter = stockIncreaseFilter
        self.shopifyInventoryId = shopifyInventoryId
        self.shopifyLocationId = shopifyLocationId
        self.bcInventoryValue = None
        self.flags = []
        self.debug = debug
        self.apiType = apiType

    # Does what it says on the tin. If it doesnt work, maybe check the way the level variable is being unpacked
    def getBcStockLevels(self):

        try:
            level = APITools.bcGetRequest(APITools.urlFilterByCpCodeSKU(
                "REDACTED_URL",
                self.sku.upper()))
            level = level.json()['value']
            self.bcInventoryValue = int(level[0]["currentStockAvaliable"])

            if self.debug:
                databaseHandler.setLogsToDatabase("[UP][DEBUG]BCInventoryValue",
                                                   "BC Inventory value set to " + str(
                                                       self.bcInventoryValue) + " for SKU " + self.sku)

        except Exception as e:

            # In WAL, this happens alot as WAL has SKUs that don't necessarily exist in BC.
            if self.debug:
                databaseHandler.setLogsToDatabase("[UP][ERROR]BCInventoryValue",
                                                   "BC Inventory value error was " + str(e) + " for SKU " + self.sku)
            self.flags.append("F")

    # Again, does what it says on the tin. If theres an issue and a faliure, there will be a flag F appended. Default returns
    # the response
    def postStockUpdateToShopify(self):

        if "F" in self.flags:
            return None

        try:
            headers = APITools.constructHTTPComponent("H", [["Content-Type", "application/json"]])
            body = APITools.constructHTTPComponent("B", [["location_id", int(self.shopifyLocationId)],
                                                                     ["inventory_item_id", self.shopifyInventoryId],
                                                                     ["available", self.bcInventoryValue]])
            a = self.shopifyApiTools.constructShopifyPostRequest("inventory_levels/set.json", headers, body, self.apiType)

            if self.debug:
                databaseHandler.setLogsToDatabase("[UP][DEBUG]PostStockUpdate",
                                                   "Post stock update was successful for SKU " + self.sku)

            return a.json()

        except Exception as e:

            databaseHandler.setLogsToDatabase("[UP][ERROR]PostStockUpdate",
                                               "Post stock update error was " + str(e) + " for SKU " + self.sku)

            self.flags.append("F")
            return None

    def getShopifyStock(self):

        # Whether this code is janky or not, you decide. Essentially, a is a variable that exists to contain
        # shopify get request data, but in order for python to not have a nervous breakdown it has to be defined
        # to enter the while loop. The while loop tries 20 times to request shopify for data with "inventory_levels"
        # in it. Once it recieves it, the loop will be broken. It is sleeping for 0.2 as shopify only allows 2 reqs per second.


        url = "inventory_levels.json?inventory_item_ids=" + str(
            self.shopifyInventoryId)  # + "&location_ids=Constants.SHOPIFY_LOC"

        response = self.shopifyApiTools.constructShopifyGetRequest(url, None, self.apiType)
        if len(re.findall("inventory_levels", str(response.json()))) == 0:
            raise Exception("Faliure to get stock level check. Check iterator. Error is " + str(response.json()))

        else:
            try:
                self.shopifyInventoryValue = int(response.json()["inventory_levels"][0]["available"])

            except Exception as e:

                databaseHandler.setLogsToDatabase("[UP][ERROR]PostStockUpdate",
                                                   "While fetching stock levels from shopify, an exception catch occured: " + str(
                                                       e) + " for SKU " + self.sku + " with return data of " + str(e))

                self.flags.append("F")
                self.shopifyInventoryValue = 0
                return False

            # Comapre the BC Inventory value against the shopify inventory value. If BC higher, return true, if shopify
            # is higher, return false.

    def checkIfRecentlyUpdated(self, data):

        # Uses regex matching to find if the item updated was updated today.
        # If an update has occurred, set to true.

        today = (date.today()).strftime("%Y-%m-%d")

        if len(re.findall(today, str(data))) == 1:
            return True
        else:
            return False

    def fireAtShopify(self):

        stockIncrease = 0

        # Internal functions to use apiTools to get stock levels
        self.getBcStockLevels()
        self.getShopifyStock()

        # If internal functions failed, end this now
        if "F" in self.flags:
            return 0

        # Compare inventory values; if an issue is present with one of the values, raise a flag and the function should
        # return 0.
        try:
            print(self.bcInventoryValue, self.shopifyInventoryValue)
            if self.bcInventoryValue > self.shopifyInventoryValue:
                stockIncrease = True
            else:
                stockIncrease = False

        except Exception as e:
            databaseHandler.setLogsToDatabase("[UP][WARN]SetupStockUpdate",
                                               "Comparator faliure when checking for higher BC value for SKU " + self.sku)
            self.flags.append("F")

        # If any failures occurred getting any values, there is clearly a problem so leave.
        if "F" in self.flags:
            return 0

        # Check if there is a filter on increasing stock in shopify and there is a stock increase. If so, stop the
        # process as the stock should not increase.
        if self.stockIncreaseFilter and stockIncrease:
            databaseHandler.setLogsToDatabase("[UP][WARN]SetupStockUpdate",
                                               "While posting a stock update to shopify, a higher value for BC items was "
                                               "found while Stock Increase Filter was SP:BC -> " + str(
                                                   self.shopifyInventoryValue)
                                               + ":" + str(self.bcInventoryValue) + " for SKU " + self.sku)
            return 0

        # If the stock value is the same, dont do anything
        if self.shopifyInventoryValue == self.bcInventoryValue:
            return 0

        # If all conditions are
        self.postStockUpdateToShopify()

        if "F" in self.flags:
            return 0

        databaseHandler.setLogsToDatabase("[UP][INFO]PostStockUpdate",
                                           "SKU successfully updated. SKU was: " + str(
                                               self.sku) + " with stock change from "
                                           + str(self.shopifyInventoryValue) + " to " + str(self.bcInventoryValue))

        return 1

    def getSku(self):
        return self.sku


class InventoryLevelIDPirate:

    # Essentially, shopify does not allow you to search via SKU for any product or inventory level (unless you're
    # using graphQl, weirdo) - the solution is to have a process which stores every inventory level ID we have and
    # link it to an SKU in the database. Its not pretty, but it works.

    def __init__(self, shopifyApiTools, location_id, apiType="Default", debug=True):

        self.shopifyApiTools = shopifyApiTools
        self.location_id = location_id
        self.flags = []
        self.apiType = apiType
        self.debug = debug

    def getInventoryItemIdFromProductsInLive(self):

        # I adapted this code from the original classles version. The ID of the oldest item in shopify's active
        # products is taken and the first 250 products are then fetched, and then the last ID of that batch
        # is yoinked and then so on and so forth until it cant yoink no more and it causes an error.

        totalList = []

        x = self.shopifyApiTools.constructShopifyGetRequest("products.json",
                                                            [["limit", 250], ["status", "active"],
                                                      ["order", "created_at+asc"]], self.apiType)
        x = x.json()
        for item in x["products"]:
            for variant in item["variants"]:
                totalList.append([variant["inventory_item_id"], variant["sku"]])

        limiter = False

        while not limiter:

            try:
                lastid = x["products"][-1]["id"]

                x = self.shopifyApiTools.constructShopifyGetRequest("products.json", [["limit", 250], ["status", "active"],
                                                                                      ["since_id", str(lastid)]], self.apiType)
                x = x.json()
                for item in x["products"]:
                    for variant in item["variants"]:
                        totalList.append([variant["inventory_item_id"], variant["sku"]])

            except Exception as e:
                limiter = True

        return totalList

    # Post the list of inventory ids and skus to BC
    def postInventoryIdSkuListToDatabase(self, list, wipe=False):

        try:

            if wipe:
                databaseHandler.skuShopifyInvIDTruncater()

            entries = databaseHandler.setInventoryIdSkuToDatabase(list)
            if self.debug:
                databaseHandler.setLogsToDatabase("[UP][INFO]InventoryPirate",
                                                   "While updating live sku list, new entries found were: " + str(
                                                       entries))

        except Exception as e:
            self.flags.append("F")
            databaseHandler.setLogsToDatabase("[UP][ERROR]InventoryPirate",
                                               "While updating live sku list, an error occured with posting to database: " + str(
                                                   e))

        return None

    def run(self, wipe=False):

        try:

            if self.debug:
                databaseHandler.setLogsToDatabase("[UP][DEBUG]InventoryPirate",
                                                   "Primary pirate process began.")
            self.postInventoryIdSkuListToDatabase(self.getInventoryItemIdFromProductsInLive(), wipe)
            self.flags.append("S")

            if self.debug:
                databaseHandler.setLogsToDatabase("[UP][DEBUG]InventoryPirate",
                                                   "Primary pirate process complete.")

        except Exception as e:

            self.flags.append("F")
            databaseHandler.setLogsToDatabase("[UP][ERROR]InventoryPirate",
                                               "While updating live sku list, an error occured generally: " + str(e))

        return self.flags


# Main processor class for dealing with items

class UpdateProcessor:

    def __init__(self, shopifyApiTools, location_id, debug=False):

        self.shopifyApiTools = shopifyApiTools
        self.locationId = location_id
        self.debug = debug
        self.invItemObjectList = []

    def cleanProcessor(self):

        # I dont have the highest hopes for pythons garbage handling. This should do the trick.

        self.invItemObjectList = []
        self.totalAdditions = 0

    def getAllSkusAndInvIds(self):

        self.inventoryLink = databaseHandler.getAllInventoryIDsAndSkus()

    def heavyUpdate(self):  # Go through the database of inventory ids and skus and check each one

        try:
            self.cleanProcessor()

            if self.debug:
                databaseHandler.setLogsToDatabase("[UP][DEBUG]InventoryManUpdateProcessor",
                                                   "Beginning inventory update manual v2")
            self.getAllSkusAndInvIds()
            self.makeInvItemObjects("ManualUpload")
            self.fireObjectListAtShopify()

            databaseHandler.setLogsToDatabase("[UP][DEBUG]InventoryManUpdateProcessor",
                                                   "Manual inventory v2 complete. Total updates were: " + str(
                                                       self.totalAdditions))

        except Exception as e:

            databaseHandler.setLogsToDatabase("[UP][ERROR]InventoryManUpdateProcessor",
                                               "Error for a manual V2 update. Error was:  " + str(e))

    def webhookUpdate(self, skuList):  # Specifically update a particular list of SKUs (Mainly for webhooks)

        self.cleanProcessor()
        self.inventoryLink = []
        # Inventory link is a list of all inventory items
        if self.debug:
            databaseHandler.setLogsToDatabase("[UP][DEBUG]InventorySpecUpdateProcessor",
                                               "Specific inventory v2 starting. SKU list is: " + str(skuList))

        for sku in skuList:
            try:
                shopifyInvId = databaseHandler.getInventoryIdViaSku(sku)

                if shopifyInvId is None or str(shopifyInvId) == " ":
                    if self.debug:
                        databaseHandler.setLogsToDatabase("[UP][WARN]InventorySpecUpdateProcessor",
                                                           "An SKU did not have an equivalent inventory code. SKU was: " + str(
                                                               sku))
                    continue

                if type(shopifyInvId) is type(tuple):
                    shopifyInvId = shopifyInvId[0]

                else:
                    self.inventoryLink.append([shopifyInvId, sku])

            except Exception as e:
                databaseHandler.setLogsToDatabase("[UP][ERROR]InventorySpecUpdateProcessor",
                                                   "SKU error for inventory spec updater generating links."
                                                   " Error was: " + str(
                                                       e) + " for SKU " + str(sku))
        try:
            self.makeInvItemObjects()
            if len(self.invItemObjectList) == 0:
                pass
            else:
                self.fireObjectListAtShopify()

            if self.debug:
                databaseHandler.setLogsToDatabase("[UP][DEBUG]InventorySpecUpdateProcessor",
                                                   "Specific inventory v2 complete. SKU list is: " + str(skuList))

        except Exception as e:

            databaseHandler.setLogsToDatabase("[UP][ERROR]InventorySpecUpdateProcessor",
                                               "Major inventory v2 error occured when making/firing objects."
                                               "SKU list is: " + str(skuList) + " with error of " + str(e))

    def makeInvItemObjects(self, apiType="Default"):

        for row in self.inventoryLink:
            self.invItemObjectList.append(
                InventoryItem(row[1], self.shopifyApiTools, row[0], self.locationId, False, False, apiType))

    def fireObjectListAtShopify(self):

        # Iterate through the list of objects stored in the class' variable.
        for obj in self.invItemObjectList:
            try:
                returnVal = obj.fireAtShopify()
            except Exception as e:
                databaseHandler.setLogsToDatabase("[UP][ERROR]InventorySpecUpdateProcessor",
                                                   "Specific inventory v2 error occured when making/firing objects."
                                                   " CP item was " + str(obj.getSku()) + " with an error of " + str(e))
                returnVal = 0
            self.totalAdditions += returnVal
