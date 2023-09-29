import datetime
import DBCon
#   _______________
# ((               ))
#  )) DB Handler v1.1 FOR SYNC ((
# ((               ))
#   ---------------

## NOTE, THIS VERSION OF THE DB OBJECT IS SIMPLIFIED FOR PRODUCTION AND TUNED FOR SYNCING PRODUCT STOCK LEVELS ##
# V1.1 - Split DB handler into singleton - two files.

## TODO: MERGE THIS WITH THE DBCon File

def getEventIdOrSetEventIDIfExists(event):

    # I initally built this function with recursion - unfortunatley, this caused too many bugs.
    # Now, a check takes place if the ID exists. if the check returns nothing, the new event
    # is built and its id is got.

    ID = DBCon.DBConnection.execute_query("SELECT event_id FROM event_type WHERE event_type = %s", event)
    if not ID:
        DBCon.DBConnection.execute_query("INSERT INTO event_type (event_type) VALUES (%s)", event)
        ID = DBCon.DBConnection.execute_query("SELECT event_id FROM event_type WHERE event_type = %s", event)

    return ID[0] # Database doing database things and returning arrays

def setLogsToDatabase(eventName, content):

    # Check which table is passed in as a parameter, push the event to the database.

    DBCon.DBConnection.execute_query("INSERT INTO event_logs (event_id, time, content) VALUES (%s, %s, %s)",
                         [getEventIdOrSetEventIDIfExists(eventName), str(datetime.datetime.now()), content], False)

def setInventoryIdSkuToDatabase(list):

    counter = 0
    # Goes through each entry in the relation table and tries to push it. If it already exists,
    # an error should be caused. Return the amount of successful additions.
    sql = "INSERT INTO sku_shopify_relation (inventory_item_id, sku) VALUES (%s, %s)"
    for entry in list:
        try:
            DBCon.DBConnection.execute_query(sql, entry, False)
            counter+=1
        except Exception as e:
            pass
    return counter

def getInventoryIdViaSku(sku):

    sql = "SELECT inventory_item_id FROM sku_shopify_relation WHERE sku = %s"
    return DBCon.DBConnection.execute_query(sql, [sku])

def getMostRecentInsertId():
    sql = "SELECT LAST_INSERT_ID()"
    return DBCon.DBConnection.execute_query(sql, None, False)

def getAllInventoryIDsAndSkus():

    sql = "SELECT * FROM sku_shopify_relation"
    return DBCon.DBConnection.execute_query(sql, None, True)

def skuShopifyInvIDTruncater():
    sql = "TRUNCATE TABLE sku_shopify_relation"
    DBCon.DBConnection.execute_query(sql, None, False)

def logTableTruncater():
    sql = "TRUNCATE TABLE event_logs"
    DBCon.DBConnection.execute_query(sql, None, False)

def setWebhookSubscription(endpoint, sub_id, secret, event_type, expires):
    sql = "INSERT INTO subscription_table (endpoint, sub_id, secret, event_type, expires) VALUES (%s, %s, %s, %s, %s)"
    DBCon.DBConnection.execute_query(sql, [endpoint, sub_id, secret, event_type, expires], False)

def getWebhookSubscriptionWithEventType(event_type):
    sql = "SELECT * FROM subscription_table WHERE event_type = %s"
    return DBCon.DBConnection.execute_query(sql, [event_type])

def updateWebhookSubscriptionExpiry(id, expires):
    sql = "UPDATE subscription_table SET expires = %s WHERE id = %s"
    DBCon.DBConnection.execute_query(sql, [expires, id], False)

def deleteWebhookSubscription(id):
    sql = "DELETE FROM subscription_table WHERE id = %s"
    DBCon.DBConnection.execute_query(sql, [id], False)