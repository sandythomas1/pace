"""Stop the local PACE service without deleting saved data."""
import http.cookiejar
import json
import urllib.request

url = 'http://127.0.0.1:8765'
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
try:
    opener.open(url, timeout=3).close()
    state = json.load(opener.open(url + '/api/state', timeout=3))
    request = urllib.request.Request(url + '/api/shutdown', b'{}', headers={'Content-Type':'application/json', 'X-CSRF-Token':state['csrf']})
    opener.open(request, timeout=3).close()
    print('PACE stopped. Your runs and Garmin session are saved.')
except Exception:
    print('PACE is not running, or could not be reached.')
