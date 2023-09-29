import APITools
import databaseHandler
import datetime

class WebhookSubscription:

    def __init__(self, endpoint, event_type, sub_id, secret, expires_at, url, id):

        self.endpoint = endpoint
        self.event_type = event_type
        self.sub_id = sub_id
        self.secret = secret
        self.expires_at = expires_at
        self.event_type = event_type
        self.url = url
        self.id = id

    def getEndpoint(self):
        return self.endpoint

    def getSecret(self):
        return self.secret

    def getSubscriptionId(self):
        return self.sub_id

    def getExpiresAt(self):
        return self.expires_at

    def getId(self):
        return self.id

    def setExpiresAt(self, expires_at):
        self.expires_at = expires_at
        databaseHandler.updateWebhookSubscriptionExpiry(self.id, expires_at)

    def patchSubscription(self):

        request = APITools.bcPatchRequest(self.sub_id, self.url, self.secret)
        databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "PATCH Request retruned status code of: " + str(request.status_code) + " and request data of: " + str(request.json()))
        if int(request.status_code) == 200 and request.json()['clientState'] == self.secret:
            databaseHandler.updateWebhookSubscriptionExpiry(self.id, request.json()['expirationDateTime'])
            return True
        else:
            return False

    def deleteSubscription(self):

        databaseHandler.deleteWebhookSubscription(self.id)



class WebhookFactory:

    def __init__(self, hookUrl = "URL_REDACTED", debug=True):

        self.debug = debug
        self.hookUrl = hookUrl

    def createWebhook(self, event_type):

        # TODO: IMPLEMENT EVENT TYPE FOR FUTURE WEB HOOKS

        self.generateSecretAndNotifEndpoint()
        try:
            request = APITools.bcHookPost(self.hookUrl + self.notifEndpoint, self.secret)
        except Exception as e:
            databaseHandler.setLogsToDatabase("[UP][ERROR]FlaskUpdater", "Error creating webhook: " + str(e))
            raise e

        if int(request.status_code) == 201 and request.json()['clientState'] == self.secret:

            try:
                databaseHandler.setWebhookSubscription(self.notifEndpoint, request.json()['subscriptionId'], self.secret, "itemStockLevels", request.json()['expirationDateTime'])
                id = databaseHandler.getMostRecentInsertId()
            except Exception as e:
                databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "Error setting webhook subscription: " + str(e))
                raise Exception("Error setting webhook subscription: " + str(e))

            databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "Webhook created. Details are: " + str(request.json()) +
                                              " with notification endpoint " + self.notifEndpoint + " and secret " + self.secret + " ID is " + str(id))

            return WebhookSubscription(self.notifEndpoint, event_type, request.json()['subscriptionId'], self.secret, request.json()['expirationDateTime'], self.hookUrl + self.notifEndpoint, id)

        else:
            databaseHandler.setLogsToDatabase("[UP][ERROR]FlaskUpdater", "Error creating webhook: " + str(request.json()))
            raise Exception("Error creating webhook: " + str(request.json()))

    def generateSecretAndNotifEndpoint(self):

        import uuid
        import secrets
        self.notifEndpoint = str(uuid.uuid4())
        self.secret = secrets.token_urlsafe(64)
        databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "Shared secet and notification endpoint generated."
                                                                    " Secret is: " + str(self.secret) +
                                          " with notification endpoint " + self.notifEndpoint)
        return None

    def getSubscriptionByEventType(self, event_type):

        try:
            subscription = databaseHandler.getWebhookSubscriptionWithEventType(event_type)

            if subscription is None:
                try:
                    databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "No webhook subscription found for event type " + event_type + ". Creating new one.")
                    newSub = self.createWebhook(event_type)
                    return newSub
                except Exception as e:
                    databaseHandler.setLogsToDatabase("[UP][ERROR]FlaskUpdater", "Had to create new webhook - no existing found. Error creating webhook: " + str(e))
                    raise e
            subscription = WebhookSubscription(subscription[1], subscription[4], subscription[2], subscription[3], subscription[5], self.hookUrl + subscription[1], subscription[0])

            # TODO: CONFIRM BELOW ACTUALLY WORKS
            if datetime.datetime.strptime(subscription.getExpiresAt(), "%Y-%m-%dT%H:%M:%SZ") < datetime.datetime.now():
                try:
                    databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "Webhook subscription expired. Deleting subscription of ID " + str(subscription.getSubscriptionId()))
                    subscription.deleteSubscription()
                except Exception as e:
                    databaseHandler.setLogsToDatabase("[UP][ERROR]FlaskUpdater", "Had to delete expired webhook subscription, but an error occured: " + str(e))
                    raise e
                self.getSubscriptionByEventType(event_type)
            databaseHandler.setLogsToDatabase("[UP][INFO]FlaskUpdater", "Flask came out of webhook processing with webhook data of: " + str(subscription.getSubscriptionId()))
            return subscription

        except Exception as e:
            databaseHandler.setLogsToDatabase("[UP][ERROR]FlaskUpdater", "Error getting webhook subscription: " + str(e))
            raise e
