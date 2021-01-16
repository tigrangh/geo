from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
import requests, json, enum, time, math
import configparser
import sqlite3

class Config:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('geo.ini')

        self.dbUrl = ''

        if 'db' in config and 'url' in config['db']:
            self.dbUrl = config['db']['url']

class Reader:
    def __init__(self, config):
        self.config = config
        
    def getLocations(self):

        locations = []

        connection = sqlite3.connect(self.config.dbUrl)
        
        try:
            cursor = connection.execute('select mobilecountrycode, mobilenetworkcode, locationareacode, cellid, latitude, longitude, accuracy, source from gsm')

            for row in cursor:
                locations.append({
                    'mcc': row[0],
                    'mnc': row[1],
                    'lac': row[2],
                    'cellid': row[3],
                    'lat': row[4],
                    'lng': row[5],
                    'accuracy': row[6],
                    'source': row[7]
                })
        finally:
            connection.close()

        return locations

class main:
    def __init__(self):
        self.config = Config()
        self.reader = Reader(self.config)

        locations = self.reader.getLocations()

        print('<?xml version="1.0" encoding="UTF-8"?>')
        print('<kml xmlns="http://www.opengis.net/kml/2.2">')
        print('  <Document>')
        print('    <name>gsm towers</name>')
        for location in locations:
            print('    <Placemark>')
            print('      <name>cellid: {}</name>'.format(location['cellid']))
            print('      <description>{}</description>'.format(location))
            print('      <Point>')
            print('        <coordinates>{},{},0</coordinates>'.format(location['lng'], location['lat']))
            print('      </Point>')
            print('    </Placemark>')
        print('  </Document>')
        print('</kml>')

if __name__ == '__main__':
    m = main()

