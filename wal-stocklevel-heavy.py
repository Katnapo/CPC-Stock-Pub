from Updater import UpdateProcessor, InventoryLevelIDPirate
from APITools import ShopifyApiHelper
import databaseHandler
import time

databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater",
                                  "The heavy updater with pirate process was started.")
heavyUpdater = UpdateProcessor(ShopifyApiHelper(), 65904673012)
pirate = InventoryLevelIDPirate(ShopifyApiHelper(), 65904673012)
pirate.run(True)
time.sleep(60)
heavyUpdater.heavyUpdate()
databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater",
                                  "The heavy updater with pirate process finished.")