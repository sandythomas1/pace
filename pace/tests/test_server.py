import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Database, GarminSync, AppServer, normalize_garmin, import_file, validate_run, protect, valid_date

def activity(i, distance=5000):
    return {'activityId': i, 'activityType': {'typeKey': 'running'}, 'activityName':'A real run',
            'startTimeLocal':'2026-09-09 07:00:00','distance':distance,'duration':1800,'averageHR':145}

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_database_survives_reopen_and_sync_keeps_reflection(self):
        r = normalize_garmin(activity(1))
        self.assertTrue(self.db.save(r))
        r.update(notes='Felt good',kind='Tempo',rpe=7,shoe='trainers')
        self.db.save(r)
        self.assertFalse(self.db.save(normalize_garmin(activity(1,5100)),preserve=True))
        saved=Database(self.tmp.name).get('garmin:1')
        self.assertEqual(saved['notes'],'Felt good')
        self.assertEqual(saved['distance_m'],5100)
        self.assertEqual(saved['kind'],'Tempo')
        self.assertEqual(len(self.db.list()),1)

    def test_no_demo_records_in_database(self):
        self.assertEqual(self.db.list(),[])
        self.assertTrue(self.db.settings()['preview'])

    def test_new_install_has_no_personal_race(self):
        settings=self.db.settings()
        self.assertIsNone(settings['race_date'])
        self.assertEqual(settings['race_location'],'')
        self.assertEqual(settings['race_url'],'')

    def test_non_running_activity_is_excluded(self):
        a=activity(1);a['activityType']['typeKey']='cycling'
        self.assertIsNone(normalize_garmin(a))

    def test_csv_units_and_repeat_import_identity(self):
        data='Activity Type,Date,Title,Distance,Time,Avg HR\nRunning,2026-09-09 07:00:00,Park loop,3.1,00:30:00,145\nCycling,2026-09-09,Bike,10,01:00:00,125'
        a=import_file('runs.csv',data,'mi');b=import_file('runs.csv',data,'mi')
        self.assertEqual(len(a),1);self.assertAlmostEqual(a[0]['distance_m'],4988.9664)
        self.assertEqual(a[0]['id'],b[0]['id'])
        self.assertEqual(a[0]['duration_s'],1800)

    def test_tcx_and_gpx(self):
        tcx='<TrainingCenterDatabase><Activities><Activity Sport="Running"><Id>2026-09-09T07:00:00</Id><Lap><TotalTimeSeconds>600</TotalTimeSeconds><DistanceMeters>1600</DistanceMeters></Lap><Lap><TotalTimeSeconds>400</TotalTimeSeconds><DistanceMeters>1000</DistanceMeters></Lap></Activity></Activities></TrainingCenterDatabase>'
        r=import_file('run.tcx',tcx,'mi')[0]
        self.assertEqual((r['distance_m'],r['duration_s']),(2600,1000))
        gpx='<gpx><trk><trkseg><trkpt lat="0" lon="0"><time>2026-09-09T07:00:00Z</time></trkpt><trkpt lat="0" lon="0.01"><time>2026-09-09T07:10:00Z</time></trkpt></trkseg></trk></gpx>'
        r=import_file('run.gpx',gpx,'mi')[0]
        self.assertAlmostEqual(r['distance_m'],1111.95,places=1)
        self.assertEqual(r['duration_s'],600)

    def test_import_validates_all_records_before_write(self):
        r=normalize_garmin(activity(1))
        with self.assertRaises(ValueError):
            import_file('runs.json',json.dumps([r,{'date':'bad'}]),'mi')
        self.assertEqual(self.db.list(),[])

    def test_non_finite_and_invalid_dates_rejected(self):
        r=normalize_garmin(activity(1))
        for value in (float('nan'),float('inf'),-1,0):
            with self.assertRaises(ValueError):
                validate_run({**r,'distance_m':value})
        with self.assertRaises(ValueError): valid_date('2026-02-30')

    def test_dpapi_round_trip(self):
        raw=b'private-session-token-test'*100
        try:
            encrypted=protect(raw)
        except OSError as error:
            self.skipTest(f'This Windows launch denies DPAPI: error {error.errno}. In-memory fallback tested separately.')
        self.assertNotIn(raw,encrypted)
        self.assertEqual(protect(encrypted,decrypt=True),raw)

    def test_denied_encryption_never_writes_plaintext_and_sync_survives(self):
        sync=GarminSync(self.db)
        class Fake:
            def dumps(self):return 'SECRET_TOKEN'
        class Wrapper:client=Fake()
        sync.client=Wrapper()
        with patch('server.protect',side_effect=OSError(5,'Access denied')):
            sync.persist()
        self.assertFalse(sync.tokens.exists())
        self.assertFalse(sync.state['session_persisted'])
        self.assertIn('Sync works',sync.state['storage_message'])

    def test_paged_sync_and_offline_catchup_keep_notes(self):
        class FakeClient:
            def __init__(self): self.data=[activity(i) for i in range(230,0,-1)];self.client=self;self.calls=[]
            def get_activities(self,start,limit,**kw):self.calls.append(start);return self.data[start:start+limit]
            def dumps(self):return '{}'
        sync=GarminSync(self.db);sync.client=FakeClient()
        with patch('server.time.sleep'):
            sync.sync()
        self.assertEqual(sync.state['status'],'connected')
        self.assertEqual(len(self.db.list()),230)
        self.assertEqual(sync.client.calls,[0,100,200])
        self.assertTrue(self.db.settings()['history_complete'])
        r=self.db.get('garmin:220');r['notes']='Keep this';self.db.save(r)
        sync.client.data=[activity(i) for i in range(380,0,-1)]
        with patch('server.time.sleep'):sync.sync()
        self.assertEqual(len(self.db.list()),380)
        self.assertEqual(sync.state['imported'],150)
        self.assertEqual(self.db.get('garmin:220')['notes'],'Keep this')
        sync.disconnect()
        self.assertFalse(sync.tokens.exists())
        self.assertEqual(len(self.db.list()),380)

    def test_failed_backfill_resumes_without_losing_old_pages(self):
        class FakeClient:
            fail=True
            def __init__(self):self.client=self
            def get_activities(self,start,limit,**kw):
                if start==100 and self.fail:raise ConnectionError('no network')
                return [activity(i) for i in range(230,0,-1)][start:start+limit]
            def dumps(self):return '{}'
        sync=GarminSync(self.db);sync.client=FakeClient()
        with patch('server.time.sleep'):sync.sync()
        self.assertEqual(sync.state['status'],'error')
        self.assertFalse(self.db.settings().get('history_complete',False))
        self.assertEqual(len(self.db.list()),100)
        sync.client.fail=False
        with patch('server.time.sleep'):sync.sync()
        self.assertEqual(len(self.db.list()),230)
        self.assertTrue(self.db.settings()['history_complete'])

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();db=Database(self.tmp.name)
        self.server=AppServer(('127.0.0.1',0),db,GarminSync(db))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.port=self.server.server_address[1]
        _,headers,_=self.request('GET','/')
        self.cookie=headers['Set-Cookie'].split(';')[0]

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def request(self,method,path,data=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        h={'Content-Type':'application/json',**(headers or {})}
        conn.request(method,path,json.dumps(data).encode() if data is not None else None,h)
        r=conn.getresponse();out=(r.status,dict(r.getheaders()),r.read());conn.close();return out

    def auth(self):return {'Cookie':self.cookie,'X-CSRF-Token':self.server.csrf}

    def test_read_requires_session(self):
        self.assertEqual(self.request('GET','/api/state')[0],401)
        code,_,body=self.request('GET','/api/state',headers=self.auth())
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['runs'],[])

    def test_course_assets_are_available_locally_without_relaxing_csp(self):
        for path in ('/course.js', '/course-data.js', '/course-view.js', '/course.css', '/mission-inn-2026.jpg'):
            code, headers, body = self.request('GET', path)
            self.assertEqual(code, 200, path)
            self.assertGreater(len(body), 50)
            self.assertIn("connect-src 'self'", headers['Content-Security-Policy'])
            self.assertIn("img-src 'self' data:", headers['Content-Security-Policy'])
            if path.endswith('.jpg'):
                self.assertEqual(headers['Content-Type'], 'image/jpeg')
                self.assertTrue(body.startswith(b'\xff\xd8'))

    def test_cross_origin_and_missing_csrf_rejected(self):
        self.assertEqual(self.request('GET','/',headers={'Host':'attacker.example'})[0],403)
        self.assertEqual(self.request('POST','/api/settings',{'units':'km'},headers={'Cookie':self.cookie})[0],403)
        self.assertEqual(self.request('POST','/api/settings',{'units':'km'},headers={**self.auth(),'Origin':'https://attacker.example'})[0],403)
        self.assertEqual(self.server.db.settings()['units'],'mi')

    def test_race_link_requires_https_and_rejects_embedded_credentials(self):
        for value in ('javascript:alert(1)','http://example.com','https://user:password@example.com'):
            self.assertEqual(self.request('POST','/api/settings',{'race_url':value},self.auth())[0],400)
        self.assertEqual(self.request('POST','/api/settings',{'race_url':'https://example.com/race','race_date':None},self.auth())[0],200)
        self.assertIsNone(self.server.db.settings()['race_date'])

    def test_no_filesystem_exposure(self):
        for p in ('/server.py','/.data/pace.sqlite3','/../server.py','/%2e%2e/server.py'):
            self.assertEqual(self.request('GET',p,headers=self.auth())[0],404)

    def test_run_planner_and_export(self):
        payload={'name':'Test run','date':'2026-09-09T07:00','distance_m':5000,'duration_s':1800,'kind':'Easy'}
        code,_,body=self.request('POST','/api/runs/save',payload,self.auth())
        self.assertEqual(code,200);id=json.loads(body)['id']
        self.assertEqual(self.request('POST','/api/runs/save',{'id':id,'notes':'A useful reflection'},self.auth())[0],200)
        self.assertEqual(self.server.db.get(id)['notes'],'A useful reflection')
        self.assertEqual(self.request('POST','/api/plans/save',{'date':'2026-10-01','title':'Easy run','kind':'Easy','distance_m':5000},self.auth())[0],200)
        code,headers,body=self.request('GET','/api/export',headers=self.auth())
        backup=json.loads(body)
        self.assertEqual(len(backup['runs']),1);self.assertEqual(len(backup['plans']),1)
        self.assertNotIn('csrf',backup);self.assertNotIn('garmin-session',body.decode())
        self.assertFalse(self.server.db.settings()['preview'])

    def test_garmin_measurements_cannot_be_overwritten_by_journal(self):
        self.server.db.save(normalize_garmin(activity(1)))
        code,_,_=self.request('POST','/api/runs/save',{'id':'garmin:1','notes':'Local note','distance_m':99,'kind':'Tempo'},self.auth())
        self.assertEqual(code,200)
        self.assertEqual(self.server.db.get('garmin:1')['distance_m'],5000)
        self.assertEqual(self.server.db.get('garmin:1')['notes'],'Local note')

if __name__=='__main__':unittest.main()
