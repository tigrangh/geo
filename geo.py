from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
import requests, json, enum, time
import configparser
import sqlite3

class ResponseType(enum.Enum):
    universal = 1
    unwiredlabs = 2
    opencellid = 3

class Config:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('geo.ini')

        self.responseType = ResponseType.universal

        self.rawUrl = ''
        self.googleUrl = ''
        self.unwiredLabsUrl = ''
        self.unwiredLabsKey = ''
        self.openCellIdUrl = ''
        self.dbUrl = ''

        self.adjustSignalStrength = 0
        self.minSignalStrength = 0
        self.maxSignalStrength = 200

        self.port = 8118
        self.interface = '127.0.0.1'


        if 'raw' in config and 'url' in config['raw']:
            self.rawUrl = config['raw']['url']
        if 'google' in config and 'url' in config['google']:
            self.googleUrl = config['google']['url']
        if 'unwiredlabs' in config and 'url' in config['unwiredlabs']:
            self.unwiredLabsUrl = config['unwiredlabs']['url']
        if 'unwiredlabs' in config and 'key' in config['unwiredlabs']:
            self.unwiredLabsKey = config['unwiredlabs']['key']
        if 'opencellid' in config and 'url' in config['opencellid']:
            self.openCellIdUrl = config['opencellid']['url']
        if 'db' in config and 'url' in config['db']:
            self.dbUrl = config['db']['url']

        if 'misc' in config and 'adjust_signal_strength' in config['misc']:
            self.adjustSignalStrength = float(config['misc']['adjust_signal_strength'])
        if 'misc' in config and 'min_signal_strength' in config['misc']:
            self.minSignalStrength = float(config['misc']['min_signal_strength'])
        if 'misc' in config and 'max_signal_strength' in config['misc']:
            self.maxSignalStrength = float(config['misc']['max_signal_strength'])

        if 'http' in config and 'port' in config['http']:
            self.port = int(config['http']['port'])
        if 'http' in config and 'interface' in config['http']:
            self.interface = config['http']['interface']

    def getGoogleRequest(self, locationInfo):
        if self.googleUrl == '':
            raise Exception('empty google config')

        url = self.googleUrl
        body = {
            'radioType': 'gsm',
            'considerIp': False,
            'cellTowers': [
                {
                    'cellId': locationInfo['tower']['cellId'],
                    'locationAreaCode': locationInfo['tower']['locationAreaCode'],
                    'mobileCountryCode': locationInfo['tower']['mobileCountryCode'],
                    'mobileNetworkCode': locationInfo['tower']['mobileNetworkCode']
                    #'signalStrength': locationInfo['signalStrength']
                }
            ]
        }

        return url, body

    def getUnwiredLabsRequest(self, locationInfo):
        if self.unwiredLabsUrl == '' or self.unwiredLabsKey == '':
            raise Exception('empty unwiredlabs config')

        url = self.unwiredLabsUrl
        body = {
            'token': self.unwiredLabsKey,
            'radio': 'gsm',
            'mcc': locationInfo['tower']['mobileCountryCode'],
            'mnc': locationInfo['tower']['mobileNetworkCode'],
            #'address': 1,
            'cells': [
                {
                    'cid': locationInfo['tower']['cellId'],
                    'lac': locationInfo['tower']['locationAreaCode']
                }
            ]
        }

        return url, body
    
    def getOpenCellIdRequest(self, locationInfo):
        raise Exception('empty opencellid config')

    def fixSignalStrength(self, signalStrength):
        signalStrengthResult = signalStrength + self.adjustSignalStrength;

        if signalStrengthResult < self.minSignalStrength:
            signalStrengthResult = self.minSignalStrength
        if signalStrengthResult > self.maxSignalStrength:
            signalStrengthResult = self.maxSignalStrength

        return signalStrengthResult


def getInput(body, config):
    result = []

    body_json = json.loads(body)

    if 'cells' in body_json:
        for body_cell in body_json['cells']:
            signalStrength = config.fixSignalStrength(body_cell['signalStrength']);

            result.append({
                'signalStrength': signalStrength,
                'tower': {
                    'cellId': body_cell['cid'],
                    'locationAreaCode': body_cell['lac'],
                    'mobileNetworkCode': body_cell['mnc'],
                    'mobileCountryCode': body_cell['mcc']
                }
            })

            config.responseType = ResponseType.unwiredlabs
            
    elif 'cellTowers' in body_json:
        for body_cell in body_json['cellTowers']:
            signalStrength = config.fixSignalStrength(body_cell['signalStrength']);

            result.append({
                'signalStrength': signalStrength,
                'tower': {
                    'cellId': body_cell['cellId'],
                    'locationAreaCode': body_cell['locationAreaCode'],
                    'mobileNetworkCode': body_cell['mobileNetworkCode'],
                    'mobileCountryCode': body_cell['mobileCountryCode']
                }
            })

            config.responseType = ResponseType.universal
    else:
        raise Exception('unrecognized input: {}'.format(body))

    if not result:
        raise Exception('unrecognized input: {}'.format(body))

    return result

def processInput(input, config, persistence):

    requested = False

    all_locations = []

    for locationInfo in input:
        locations = persistence.getLocations(locationInfo)

        tower = locationInfo['tower']
        print('got {} cached locations for {}'.format(len(locations), tower))

        location = {}

        if not locations and not requested and config.unwiredLabsUrl:
            requestUrl, requestBody = config.getUnwiredLabsRequest(locationInfo)
            
            print('Requesting unwired labs')
            print(requestUrl)
            print(json.dumps(requestBody))
            response = requests.post(requestUrl, data=json.dumps(requestBody), headers={'Content-Type': 'application/json'})
            print('Response')
            print(response.content.decode('utf-8'))

            if response.ok:
                response_json = response.json()

                if response_json['status'] == 'ok':
                    location = {
                        'location': {
                            'lat': response_json['lat'],
                            'lng': response_json['lon']
                        },
                        'accuracy': response_json['accuracy'],
                        'signalStrength': locationInfo['signalStrength'],
                        'source': 'unwiredlabs.com'
                    }

                    requested = True
        
        if not locations and not requested and config.googleUrl:
            requestUrl, requestBody = config.getGoogleRequest(locationInfo)
            
            print('Requesting google')
            print(requestUrl)
            print(json.dumps(requestBody))
            response = requests.post(requestUrl, data=json.dumps(requestBody), headers={'Content-Type': 'application/json'})
            print('Response')
            print(response.content.decode('utf-8'))

            if response.ok:
                response_json = response.json()

                location = {
                    'location': {
                        'lat': response_json['location']['lat'],
                        'lng': response_json['location']['lng']
                    },
                    'accuracy': response_json['accuracy'],
                    'signalStrength': locationInfo['signalStrength'],
                    'source': 'google.com'
                }
                requested = True
        
        if location:
            locations.append(location)
            persistence.saveLocation(tower, location)

        all_locations.extend(locations)
    
    #for
    mean_location = {
        'location': {
            'lat': 0,
            'lng': 0
        },
        'accuracy': 0
    }

    if not all_locations:
        raise Exception('got no locations during processing')

    all_signalStrength = 0
    for location in all_locations:
        all_signalStrength += location['signalStrength']

    print('locations count: {}'.format(len(all_locations)))
    print('average signal strength: {}'.format(all_signalStrength / len(all_locations)))

    for location in all_locations:
        mean_location['location']['lat'] += location['location']['lat'] / all_signalStrength * location['signalStrength']
        mean_location['location']['lng'] += location['location']['lng'] / all_signalStrength * location['signalStrength']
        mean_location['accuracy'] += location['accuracy'] / all_signalStrength * location['signalStrength'] / len(all_locations)
    
    if config.responseType == ResponseType.universal:
        responseBody = json.dumps(mean_location)
    elif config.responseType == ResponseType.unwiredlabs:
        responseBody = json.dumps({
            'status': 'ok',
            'lat': mean_location['location']['lat'],
            'lon': mean_location['location']['lng'],
            'accuracy': mean_location['accuracy']
        })


    return responseBody


class Persistence:
    def __init__(self, config):
        self.config = config
        connection = sqlite3.connect(self.config.dbUrl)

        try:
            cursor = connection.execute('create table if not exists gsm (id integer primary key, mobilecountrycode integer not null, mobilenetworkcode integer not null, locationareacode integer not null, cellid integer not null, latitude real not null, longitude real not null, accuracy real not null, source varchar not null, timestamp integer not null)')
            connection.commit()
        finally:
            connection.close()
        
    def getLocations(self, locationInfo):
        tower = locationInfo['tower']

        locations = []

        connection = sqlite3.connect(self.config.dbUrl)
        
        try:
            condition = (tower['mobileCountryCode'], tower['mobileNetworkCode'], tower['locationAreaCode'], tower['cellId'])
            cursor = connection.execute('select latitude, longitude, accuracy from gsm where mobilecountrycode = ? and mobilenetworkcode = ? and locationareacode = ? and cellid = ?', condition)

            for row in cursor:
                locations.append({
                    'location': {
                        'lat': row[0],
                        'lng': row[1]
                    },
                    'accuracy': row[2],
                    'signalStrength': locationInfo['signalStrength']
                })
        finally:
            connection.close()

        return locations

    def saveLocation(self, tower, location):
        connection = sqlite3.connect(self.config.dbUrl)
        
        try:
            row = (
                tower['mobileCountryCode'],
                tower['mobileNetworkCode'],
                tower['locationAreaCode'],
                tower['cellId'],
                location['location']['lat'],
                location['location']['lng'],
                location['accuracy'],
                location['source'],
                int(time.time()))

            cursor = connection.executemany('insert into gsm (mobilecountrycode, mobilenetworkcode, locationareacode, cellid, latitude, longitude, accuracy, source, timestamp) values(?, ?, ?, ?, ?, ?, ?, ?, ?)', [row])
            connection.commit()
        finally:
            connection.close()

class CachingServer:
    def __init__(self, persistence, config):
        self.stop = False
        self.config = config

        CachingHandler.persistence = persistence
        CachingHandler.config = config
        self.httpd = HTTPServer((config.interface, config.port), CachingHandler)

        try:
            while not self.stop:
                self.httpd.handle_request()
        except:
            print('')
            print('shutting down')


class CachingHandler(BaseHTTPRequestHandler):
    persistence = None
    config = None

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Hello, world!')


    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        requestBody = self.rfile.read(content_length)
        print(requestBody.decode('utf-8'))

        responseCode = ''
        responseBody = b''

        try:
            print('read input...')
            input = getInput(requestBody.decode('utf-8'), self.config)

            print('processing...')
            responseBodyStr = processInput(input, self.config, self.persistence)
            print('response')
            print(responseBodyStr)
            responseBody = responseBodyStr.encode('utf-8')
            responseCode = 200

        except Exception as ex:
            print('exception caught: {}'.format(ex))
            print('requesting raw')
            response = requests.post(self.config.rawUrl, data=requestBody, headers={'Content-Type': 'application/json'})
            print('response')
            print(response.content.decode('utf-8'))

            responseCode = response.status_code
            responseBody = response.content
        
        print('.')

        self.send_response(responseCode)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(responseBody)


class main:
    def __init__(self):
        self.config = Config()
        self.persistence = Persistence(self.config)

        self.server = CachingServer(self.persistence, self.config)

if __name__ == '__main__':
    m = main()
