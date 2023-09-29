###

Stock Synchronisation code for the WAL outlet (Branched from CPC)

##

This service was in use in different forms and versions throughout 2022 into 2023. It was used to synchronise stock levels
between CPC's ERP system and the WAL outlet.

## 

A fore note: this service isn't as well structured/clear as the sales order service or the redirect service; it wasn't
a priority to clean this up as it worked fine. Further to this, the WAL project ended before I got a chance
to refactor the code into a more understandable structure. As of writing this readme, I havent looked at this code
in almost a year. I will try to explain it as best I can, but I may miss some things.

An overview: 

- CPC's ERP system (Microsoft Dynamics Buisness Central 365) used a webhook system to inform external services of changes to the ERP system.

- This service was one of those external services; on startup, a webhook subscription would be made and written to the database, 
  the service would keep this subscription live by sending a PATCH request at regular intervals. Any changes to the ERP system
  were received by this service via the webhook, and the service would then make the appropriate API calls to Shopify to update. This was
  the primary updating method.

- The webhook service and/or the code built to manage hooks, however, was found to be unreliable. Two secondary services were
  implemented over the course of my tenure (what would be called 'sweeper services'). The first is designated in this code as "lightUpdater"; this was rudimentary 
  code intended as a quick fix made early on in my tenure. 

- The second secondary service is the 'heavy updater' and was built as a more permanent solution. This service would run
  at regular intervals and check for any changes to the ERP system since the last time it ran. This service was built
  to be more robust than the light updater and was intended to be the primary sweeper service.

