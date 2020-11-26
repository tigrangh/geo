# Geo
Geo is a small http server intended to serve geolocation API requests originating from [Traccar](https://www.traccar.org "Traccar Homepage") server.

Since the big geolocation APIs either cost money or rate limit the requests, Geo is here to handle the requests from Traccar and to cache gsm tower information received from Google Cloud or Unwired Labs APIs. Later, when the cache is sufficient the requests are handled locally by Geo only.

Geo configuration file, geo.ini, in addition to couple more settings, can specify the following
* network interface, for example 'localhost',
* the port such as 8118, 
* Google geolocation API url - https://www.googleapis.com/geolocation/v1/geolocate?key=GCLOUD_API_KEY
* Unwired Labs geolocation API url - https://us1.unwiredlabs.com/v2/process.php
* Unwired Labs geolocation API key - UNWIRED_KEY

Then we can configure traccar.xml like this
```xml
...
<properties>
    ...
    <entry key='geolocation.enable'>true</entry>
    <entry key='geolocation.type'>unwired</entry>
    <entry key='geolocation.key'>UNWIRED_KEY</entry>
    <entry key='geolocation.url'>http://127.0.0.1:8118</entry>
    <entry key='geolocation.processInvalidPositions'>true</entry>
</properties>
```

With this, Traccar will send a request to Geo, which in turn will process the towers one by one and send a request to unwiredlabs.com or in case of failure fall back to googleapis.com, according to geo.ini configuration. Geo will try to be smart and cache each tower information, and if something unexpected happens, it will fall back to dumb proxy mode, simply to route the Traccar's raw request to unwiredlabs.com. This is why `UNWIRED_KEY` appears both in traccar.xml and in geo.ini.

The cache is collected in geo.db SQLite DB.  
Geo also mimicks triangulation to some extent.
