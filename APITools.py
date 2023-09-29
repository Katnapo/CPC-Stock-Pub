import requests
import json
import time
from constants import Constants

#   _______________
# ((               ))
#  )) API Tools v1.1 FOR SYNC ((
# ((               ))
#   ---------------

## NOTE, THIS VERSION OF THE API OBJECT IS SIMPLIFIED FOR PRODUCTION AND TUNED FOR SYNCING PRODUCT STOCK LEVELS ##
# V1.1 - Simplified for singleton use, keys stored in constant file
bcKeys = Constants.BC_KEY


def constructHTTPComponent(type, pairs):
    returnDict = {}
    for pair in pairs:
        returnDict[pair[0]] = pair[1]

    if type == "B":
        return json.dumps(returnDict)

    else:
        return returnDict


def bcGetRequest(url, type="D"):
    headers = constructHTTPComponent("H", [["Authorization", bcKeys], ["Content-Type", "application/json"]])
    response = requests.request("GET", url, headers=headers)
    return response


def bcPatchRequest(sub, notUrl, clientState):
    url = "URL_REDACTED" + sub + ")"

    payload = constructHTTPComponent("B", [["notificationUrl", notUrl], ["resource",
                                                                              "REDACTED_URL"],
                                                ["clientState", clientState]])
    headers = constructHTTPComponent("H", [["Authorization", bcKeys], ["Content-Type", 'application/json'],
                                                ["If-Match", "*"]])
    response = requests.patch(url, headers=headers, data=payload)

    return response


def bcHookPost(notUrl, clientState):
    url = "URL_REDACTED"

    payload = constructHTTPComponent("B", [["notificationUrl", notUrl], ["resource",
                                                                              "REDACTED_URL"],
                                                ["clientState", clientState]])
    headers = constructHTTPComponent("H", [["Authorization", bcKeys], ["Content-Type", 'application/json']])
    response = requests.post(url, headers=headers, data=payload)

    return response

def urlFilterByCpCodeSKU(url, sku):

    return url + "?$filter=childsplayItemNumber eq '" + sku + "'"

def urlFilterByMasterCpCodeSKU(url, msku):

    return url + "?$filter=childsplayMasterItemNumber eq '" + msku + "'"


class ShopifyApiHelper:

    # TODO: MAKE THIS INTO A TRUE SINGLETON

    def __init__(self):

        self.shopifyUrl = Constants.WAL_URL
        self.bcKeys = Constants.BC_KEY
        self.lastShopifyUse = time.time()
        self.debug = True

    def apiRestrictor(self):

        while time.time() - self.lastShopifyUse < 0.5:
            time.sleep(0.1)
        self.lastShopifyUse = time.time()

    ## SHOPIFY API TOOLS ##

    def constructShopifyGetRequest(self, target, filterList=None, apiKey=""):

        self.apiRestrictor()

        if filterList is None:
            filterList = []

        localShopifyUrl = self.shopifyUrl

        def constructFilterList(filterList):

            if not filterList:
                return ""

            resultString = "?" + str(filterList[0][0]) + "=" + str(filterList[0][1])
            filterList.pop(0)

            for item in filterList:
                resultString = resultString + "&" + item[0] + "=" + item[1]

            return resultString


        finalUrl = localShopifyUrl + target + constructFilterList(filterList)
        response = requests.get(finalUrl)
        return response


    def constructShopifyPostRequest(self, target, headers={}, body=json.dumps({}), apiKey="Default"):

        self.apiRestrictor()

        localShopifyUrl = self.shopifyUrl

        if headers is None:
            headers = {}
        url = localShopifyUrl + target

        response = requests.post(url, headers=headers, data=body)
        return response