"""PACE: a private, loopback-only running journal and Garmin sync service."""
from __future__ import annotations

import argparse
import base64
import csv
import errno
import ctypes
import hashlib
import io
import json
import logging
import math
import mimetypes
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('PACE_DATA_DIR', ROOT / '.data'))
DEFAULTS = {'units': 'mi', 'race_name': 'Your half marathon', 'race_date': None,
            'race_location': '', 'race_url': '', 'goal_seconds': None, 'weekly_target_m': None,
            'runner_name': '', 'shoes': [], 'preview': True}
KINDS = {'Easy', 'Long run', 'Tempo', 'Intervals', 'Race', 'Recovery', 'Unclassified'}

def now():
    return datetime.now(timezone.utc).isoformat()

def number(value, name, low=0, high=1e9, optional=False):
    if value is None or value == '':
        if optional:
            return None
        raise ValueError(f'{name} is required.')
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name} must be a number.')
    if not math.isfinite(n) or not low <= n <= high:
        raise ValueError(f'{name} must be between {low:g} and {high:g}.')
    return n

def valid_date(value):
    value = str(value or '')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Enter a valid date and time.')
    if parsed.tzinfo:
        parsed = parsed.astimezone()
    return parsed.isoformat(timespec='seconds')

class Database:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / 'pace.sqlite3'
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, date TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, date TEXT NOT NULL, data TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        try:
            with db:
                yield db
        finally:
            db.close()

    def settings(self):
        with self.connect() as db:
            return {**DEFAULTS, **{k: json.loads(v) for k, v in db.execute('SELECT key,value FROM settings')}}

    def save_settings(self, updates):
        with self.connect() as db:
            db.executemany('INSERT OR REPLACE INTO settings VALUES (?,?)', [(k, json.dumps(v)) for k, v in updates.items()])

    def list(self, table='runs'):
        assert table in ('runs', 'plans')
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute(f'SELECT data FROM {table} ORDER BY date DESC')]

    def get(self, id, table='runs'):
        assert table in ('runs', 'plans')
        with self.connect() as db:
            r = db.execute(f'SELECT data FROM {table} WHERE id=?', (id,)).fetchone()
            return json.loads(r[0]) if r else None

    def save(self, run, table='runs', preserve=False):
        assert table in ('runs', 'plans')
        with self.connect() as db:
            old = db.execute(f'SELECT data FROM {table} WHERE id=?', (run['id'],)).fetchone()
            if old and preserve:
                old = json.loads(old[0])
                for k in ('notes', 'rpe', 'shoe', 'kind', 'splits'):
                    if k in old:
                        run[k] = old[k]
            db.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?)', (run['id'], run['date'], json.dumps(run)))
            return old is None

    def delete(self, id, table='plans'):
        assert table in ('runs', 'plans')
        with self.connect() as db:
            db.execute(f'DELETE FROM {table} WHERE id=?', (id,))

def normalize_garmin(a):
    kind = (a.get('activityType') or {}).get('typeKey', '')
    if 'running' not in kind and kind != 'treadmill_running':
        return None
    return {'id': 'garmin:' + str(a['activityId']), 'source': 'Garmin Connect',
            'garmin_id': str(a['activityId']), 'name': str(a.get('activityName') or 'Run')[:200],
            'date': valid_date(a.get('startTimeLocal') or a.get('startTimeGMT')),
            'distance_m': number(a.get('distance'), 'Distance', 0, 1e6),
            'duration_s': number(a.get('duration'), 'Duration', 0, 1e7),
            'elevation_m': number(a.get('elevationGain'), 'Elevation', 0, 1e5, True),
            'hr': number(a.get('averageHR'), 'Heart rate', 0, 300, True),
            'cadence': number(a.get('averageRunningCadenceInStepsPerMinute'), 'Cadence', 0, 400, True),
            'calories': number(a.get('calories'), 'Calories', 0, 1e6, True),
            'kind': 'Unclassified', 'notes': '', 'rpe': None, 'shoe': '',
            'device': str(a.get('deviceName') or 'Garmin device'), 'activity_type': kind}

def protect(data: bytes, decrypt=False):
    """Bind Garmin tokens to the signed-in Windows user using DPAPI."""
    if os.name != 'nt':
        raise OSError(errno.ENOTSUP, 'Secure Garmin token storage requires Windows.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data)
    inp = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    if not fn(ctypes.byref(inp), None, None, None, None, 1, ctypes.byref(out)):
        raise OSError(ctypes.get_last_error(), 'Could not access secure Garmin token storage.')
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)

class DpapiStore:
    """Garmin session file encrypted for the signed-in Windows user."""
    saved_message = 'Your Garmin session is encrypted for your Windows account.'

    def __init__(self, path):
        self.path = path

    def save(self, raw: bytes):
        encrypted = protect(raw)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_bytes(encrypted)
        tmp.replace(self.path)

    def load(self):
        return protect(self.path.read_bytes(), decrypt=True) if self.path.exists() else None

    def clear(self):
        self.path.unlink(missing_ok=True)

class KeychainStore:
    """Garmin session kept as a generic password in the macOS login Keychain."""
    saved_message = 'Your Garmin session is saved in your macOS Keychain.'
    service = b'PACE Garmin session'
    not_found = -25300  # errSecItemNotFound

    def __init__(self, account: str):
        self.account = account.encode()
        c_void_pp, c_uint32_p = ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32)
        sec = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
        cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        signatures = {
            'SecKeychainFindGenericPassword': [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, c_uint32_p, c_void_pp, c_void_pp],
            'SecKeychainAddGenericPassword': [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, c_void_pp],
            'SecKeychainItemModifyAttributesAndData': [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p],
            'SecKeychainItemFreeContent': [ctypes.c_void_p, ctypes.c_void_p],
            'SecKeychainItemDelete': [ctypes.c_void_p],
        }
        for name, args in signatures.items():
            getattr(sec, name).argtypes, getattr(sec, name).restype = args, ctypes.c_int32
        cf.CFRelease.argtypes, cf.CFRelease.restype = [ctypes.c_void_p], None
        self.sec, self.cf = sec, cf

    @staticmethod
    def check(status):
        if status:
            raise OSError(status, 'Could not access the macOS Keychain.')

    def find(self, want_data=False):
        """Return (item, data); item is None when no session is stored. Caller releases item."""
        item, size, data = ctypes.c_void_p(), ctypes.c_uint32(), ctypes.c_void_p()
        status = self.sec.SecKeychainFindGenericPassword(
            None, len(self.service), self.service, len(self.account), self.account,
            ctypes.byref(size) if want_data else None, ctypes.byref(data) if want_data else None, ctypes.byref(item))
        if status == self.not_found:
            return None, None
        self.check(status)
        if not want_data:
            return item, None
        try:
            return item, ctypes.string_at(data, size.value)
        finally:
            self.sec.SecKeychainItemFreeContent(None, data)

    def save(self, raw: bytes):
        item, _ = self.find()
        if item is None:
            return self.check(self.sec.SecKeychainAddGenericPassword(
                None, len(self.service), self.service, len(self.account), self.account, len(raw), raw, None))
        try:
            self.check(self.sec.SecKeychainItemModifyAttributesAndData(item, None, len(raw), raw))
        finally:
            self.cf.CFRelease(item)

    def load(self):
        item, data = self.find(want_data=True)
        if item is not None:
            self.cf.CFRelease(item)
        return data

    def clear(self):
        item, _ = self.find()
        if item is None:
            return
        try:
            self.check(self.sec.SecKeychainItemDelete(item))
        finally:
            self.cf.CFRelease(item)

class MemoryOnlyStore:
    """No trusted OS secret storage: keep the session in memory and never write plaintext."""
    saved_message = ''

    def save(self, raw: bytes):
        raise OSError(errno.ENOTSUP, 'Secure Garmin session storage is unavailable on this platform.')

    def load(self):
        return None

    def clear(self):
        pass

def session_store(folder: Path):
    if os.name == 'nt':
        return DpapiStore(folder / 'garmin-session.dpapi')
    if sys.platform == 'darwin':
        try:
            return KeychainStore(str(folder.resolve()))
        except OSError:
            logging.warning('macOS Keychain is unavailable; the Garmin session will stay in memory.')
    return MemoryOnlyStore()

class GarminSync:
    interval = 300

    def __init__(self, db, store=None):
        self.db = db
        self.client = None
        self.pending = None
        self.pending_time = 0
        self.auth_lock = threading.Lock()
        self.wake = threading.Event()
        self.store = store or session_store(db.folder)
        self.state = {'status': 'disconnected', 'message': 'Connect Garmin to bring your runs home.',
                      'last_sync': db.settings().get('last_sync'), 'next_sync': None,
                      'imported': 0, 'interval_seconds': self.interval, 'session_persisted': False, 'storage_message': ''}
        try:
            import garminconnect
            self.available = True
        except ImportError:
            self.available = False

    def snapshot(self):
        return {**self.state, 'available': self.available}

    def persist(self):
        try:
            self.store.save(self.client.client.dumps().encode())
            self.state.update(session_persisted=True, storage_message=self.store.saved_message)
        except OSError:
            # OS secret storage can be unavailable or denied. Keep syncing in memory; never store plaintext.
            self.state.update(session_persisted=False, storage_message='Secure session storage is unavailable on this computer. Sync works while PACE is running; sign in again after restarting PACE.')

    def begin_login(self, email, password):
        if not self.available:
            raise ValueError('Install the Garmin connector using Start PACE first.')
        if self.state['status'] in ('connecting', 'syncing'):
            raise ValueError('A connection or sync is already in progress.')
        if self.state['status'] == 'connected':
            raise ValueError('Disconnect the current Garmin account first.')
        self.state.update(status='connecting', message='Signing in to Garmin…', next_sync=None)
        threading.Thread(target=self.login, args=(email, password), daemon=True).start()

    def login(self, email, password):
        with self.auth_lock:
            try:
                from garminconnect import Garmin
                candidate = Garmin(email, password, return_on_mfa=True)
                result = candidate.login()
                candidate.password = None
                if result and result[0] == 'needs_mfa':
                    self.pending = (candidate, result[1])
                    self.pending_time = time.monotonic()
                    self.state.update(status='mfa', message='Enter the verification code Garmin sent you.')
                else:
                    self.finish_login(candidate)
            except Exception as e:
                self.fail(e, login=True)
            finally:
                password = None

    def finish_login(self, candidate):
        self.client = candidate
        self.client.password = None
        self.persist()
        self.pending = None
        self.db.save_settings({'preview': False})
        self.state.update(status='connected', message='Garmin connected. Importing your running history…')
        self.wake.set()

    def mfa(self, code):
        if not self.pending or self.state['status'] != 'mfa' or time.monotonic() - self.pending_time > 600:
            self.pending = None
            self.state.update(status='disconnected', message='The verification session expired. Sign in again.')
            raise ValueError('The verification session expired. Sign in again.')
        self.state.update(status='connecting', message='Verifying your code…')
        def run():
            with self.auth_lock:
                try:
                    candidate, context = self.pending
                    candidate.resume_login(context, code)
                    self.finish_login(candidate)
                except Exception as e:
                    self.fail(e, login=True)
        threading.Thread(target=run, daemon=True).start()

    def fail(self, e, login=False):
        name = type(e).__name__
        if 'TooManyRequests' in name:
            delay = 1800
            message = 'Garmin asked us to slow down. Retrying in 30 minutes.'
        elif 'Authentication' in name:
            delay = None
            self.client = None
            message = 'Garmin needs you to sign in again. Check your login and verification code.'
        else:
            delay = 300 if self.client and not login else None
            message = 'Could not reach Garmin. ' + ('Retrying in 5 minutes.' if delay else 'Check your connection and try signing in again.')
        self.pending = None
        self.state.update(status='error', message=message, next_sync=time.time() + delay if delay else None)
        logging.warning('Garmin operation failed (%s); credentials and response omitted.', name)

    def sync(self):
        with self.auth_lock:
            if not self.client:
                return
            self.state.update(status='syncing', message='Checking Garmin for new runs…', next_sync=None)
            try:
                known = {r['id'] for r in self.db.list() if r['source'] == 'Garmin Connect'}
                # Always scan recent pages for offline catch-up. A stored cursor resumes historical backfill.
                offset, added = 0, 0
                fresh_history = not self.db.settings().get('history_complete', False) and not self.db.settings().get('history_offset', 0)
                while True:
                    batch = self.client.get_activities(offset, 100, activitytype='running')
                    if not isinstance(batch, list):
                        raise ValueError('Unexpected Garmin activity response')
                    all_known = bool(batch)
                    for a in batch:
                        r = normalize_garmin(a)
                        if r:
                            all_known = all_known and r['id'] in known
                            added += self.db.save(r, preserve=True)
                    self.state.update(imported=added, message=f'Imported {added} runs. Reading your running history…')
                    if len(batch) < 100:
                        if fresh_history:
                            self.db.save_settings({'history_complete': True, 'history_offset': 0})
                        break
                    if all_known:
                        break
                    offset += 100
                    if fresh_history:
                        self.db.save_settings({'history_offset': offset})
                    time.sleep(1)
                # Never mark a partial backfill complete. Continue from the last committed page after a failure.
                history = self.db.settings().get('history_complete', False)
                if not history:
                    offset = int(self.db.settings().get('history_offset', 0))
                    while True:
                        batch = self.client.get_activities(offset, 100, activitytype='running')
                        if not isinstance(batch, list):
                            raise ValueError('Unexpected Garmin history response')
                        for a in batch:
                            r = normalize_garmin(a)
                            if r:
                                added += self.db.save(r, preserve=True)
                        if len(batch) < 100:
                            self.db.save_settings({'history_complete': True, 'history_offset': 0})
                            break
                        offset += 100
                        self.db.save_settings({'history_offset': offset})
                        self.state.update(imported=added, message=f'Imported {added} runs. Continuing history…')
                        time.sleep(1)
                self.persist()
                stamp = now()
                self.db.save_settings({'last_sync': stamp})
                self.state.update(status='connected', message=f'Up to date. {added} new run' + ('' if added == 1 else 's') + ' imported.',
                                  last_sync=stamp, next_sync=time.time() + self.interval, imported=added)
            except Exception as e:
                self.fail(e)

    def request_sync(self):
        if self.state['status'] == 'syncing':
            return
        if not self.client:
            raise ValueError('Connect Garmin first.')
        if self.state['status'] == 'error' and self.state['next_sync'] and self.state['next_sync'] > time.time():
            raise ValueError(self.state['message'])
        self.wake.set()

    def disconnect(self):
        if self.state['status'] in ('connecting', 'syncing'):
            raise ValueError('Wait for the current connection or sync to finish.')
        with self.auth_lock:
            self.client = None
            self.pending = None
            try:
                self.store.clear()
            except OSError:
                logging.warning('Could not remove the saved Garmin session from secure storage.')
            self.wake.clear()
            self.db.save_settings({'history_complete': False, 'history_offset': 0})
            self.state.update(status='disconnected', next_sync=None, session_persisted=False, storage_message='', message='Garmin disconnected. Your saved runs are still here.')

    def restore(self):
        with self.auth_lock:
            try:
                saved = self.store.load()
            except OSError:
                self.state.update(message='Could not read your saved Garmin session from secure storage. Connect Garmin to sign in again.')
                return
            if not saved:
                return
            try:
                from garminconnect import Garmin
                self.client = Garmin()
                self.client.login(saved.decode())
                self.state.update(status='connected', message='Restored Garmin connection.',
                                  session_persisted=True, storage_message=self.store.saved_message)
                self.wake.set()
            except Exception as e:
                self.client = None
                self.fail(e, login=True)

    def loop(self):
        if self.available:
            self.restore()
        while True:
            requested = self.wake.wait(2)
            self.wake.clear()
            due = self.state.get('next_sync')
            if self.client and (requested or (due and time.time() >= due)):
                self.sync()

def duration(text):
    if isinstance(text, (float, int)):
        return float(text)
    parts = str(text).split(':')
    if len(parts) not in (2, 3):
        return float(text)
    return sum(float(v) * 60 ** i for i, v in enumerate(reversed(parts)))

def import_file(filename, text, units):
    suffix = Path(filename).suffix.lower()
    source = 'File import'
    records = []
    scale = 1609.344 if units == 'mi' else 1000
    if suffix == '.json':
        doc = json.loads(text)
        items = doc.get('runs', doc.get('activities', [])) if isinstance(doc, dict) else doc
        if not isinstance(items, list):
            raise ValueError('The JSON file must contain a list of runs.')
        for a in items:
            if 'activityId' in a:
                r = normalize_garmin(a)
                if r:
                    records.append(r)
            else:
                records.append(a)
    elif suffix == '.csv':
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
        for a in reader:
            activity = str(a.get('Activity Type', a.get('activity_type', 'running'))).lower()
            if 'run' not in activity:
                continue
            records.append({'name': a.get('Title', a.get('name', 'Imported run')),
                            'date': a.get('Date', a.get('date')),
                            'distance_m': a.get('distance_m') or float(str(a.get('Distance', '0')).replace(',', '')) * scale,
                            'duration_s': a.get('duration_s') or duration(a.get('Time', '0')),
                            'hr': a.get('Avg HR', a.get('hr')) if a.get('Avg HR', a.get('hr')) not in ('--', '') else None})
    elif suffix in ('.tcx', '.gpx'):
        if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
            raise ValueError('XML declarations with entities are not supported.')
        root = ET.fromstring(text)
        def find(el, tag):
            node = el.find('.//{*}' + tag)
            return node.text if node is not None else None
        if suffix == '.tcx':
            for a in root.findall('.//{*}Activity'):
                if a.attrib.get('Sport', '').lower() != 'running':
                    continue
                laps = a.findall('{*}Lap')
                records.append({'name': Path(filename).stem, 'date': find(a, 'Id'),
                                'distance_m': sum(float(find(l, 'DistanceMeters') or 0) for l in laps),
                                'duration_s': sum(float(find(l, 'TotalTimeSeconds') or 0) for l in laps),
                                'hr': None})
        else:
            points = root.findall('.//{*}trkpt')
            if len(points) < 2:
                raise ValueError('This GPX does not contain a recorded track.')
            meters = 0
            for segment in root.findall('.//{*}trkseg'):
                ps = segment.findall('{*}trkpt')
                for a, b in zip(ps, ps[1:]):
                    la, lo, lb, ln = [math.radians(float(v)) for v in (a.attrib['lat'], a.attrib['lon'], b.attrib['lat'], b.attrib['lon'])]
                    h = math.sin((lb-la)/2)**2 + math.cos(la)*math.cos(lb)*math.sin((ln-lo)/2)**2
                    meters += 6371000 * 2 * math.asin(min(1, math.sqrt(h)))
            first, last = find(points[0], 'time'), find(points[-1], 'time')
            if not first or not last:
                raise ValueError('The GPX needs timestamps to calculate duration.')
            seconds = (datetime.fromisoformat(last.replace('Z', '+00:00')) - datetime.fromisoformat(first.replace('Z', '+00:00'))).total_seconds()
            records.append({'name': find(root, 'name') or Path(filename).stem, 'date': first, 'distance_m': meters, 'duration_s': seconds})
    else:
        raise ValueError('Choose a Garmin CSV, TCX, GPX, or PACE JSON export.')
    if not records:
        raise ValueError('No running activities found in this file.')
    if len(records) > 20000:
        raise ValueError('Import up to 20,000 runs at a time.')
    result = []
    for r in records:
        r = validate_run(r)
        # Stable identity makes repeated imports idempotent.
        r['id'] = r.get('id') if str(r.get('id', '')).startswith(('garmin:', 'manual:', 'import:')) else 'import:' + hashlib.sha256(f"{r['date']}|{r['distance_m']:.2f}|{r['duration_s']:.2f}".encode()).hexdigest()[:24]
        r['source'] = 'Garmin Connect' if r['id'].startswith('garmin:') else source
        result.append(r)
    return result

def validate_run(r):
    if not isinstance(r, dict):
        raise ValueError('Each run must be an object.')
    kind = r.get('kind', 'Unclassified')
    if kind not in KINDS:
        raise ValueError('Choose a valid run type.')
    return {k: v for k, v in {
        'id': str(r.get('id', ''))[:100], 'name': str(r.get('name') or 'Run')[:200],
        'date': valid_date(r.get('date')), 'distance_m': number(r.get('distance_m'), 'Distance', 1, 1e6),
        'duration_s': number(r.get('duration_s'), 'Duration', 1, 1e7),
        'hr': number(r.get('hr'), 'Heart rate', 1, 300, True),
        'elevation_m': number(r.get('elevation_m'), 'Elevation', 0, 1e5, True),
        'cadence': number(r.get('cadence'), 'Cadence', 1, 400, True),
        'calories': number(r.get('calories'), 'Calories', 0, 1e6, True),
        'kind': kind, 'notes': str(r.get('notes', ''))[:5000],
        'rpe': number(r.get('rpe'), 'Perceived effort', 1, 10, True), 'shoe': str(r.get('shoe', ''))[:100],
        'source': str(r.get('source', 'File import'))[:100], 'device': str(r.get('device', ''))[:100]
    }.items()}

class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, db, sync):
        self.db, self.sync = db, sync
        self.session = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        super().__init__(address, Handler)

class Handler(BaseHTTPRequestHandler):
    server_version = 'PACE'

    def log_message(self, *_):
        pass

    def headers_safe(self):
        port = self.server.server_address[1]
        host = self.headers.get('Host', '')
        if host not in (f'127.0.0.1:{port}', f'localhost:{port}'):
            return False
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{port}', f'http://localhost:{port}'):
            return False
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return False
        return True

    def authorized(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            value = cookie.get('pace_session')
            return bool(value and secrets.compare_digest(value.value, self.server.session))
        except Exception:
            return False

    def send(self, status, data, content_type='application/json; charset=utf-8', session=False, download=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if session:
            self.send_header('Set-Cookie', f'pace_session={self.server.session}; HttpOnly; SameSite=Strict; Path=/')
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.headers_safe():
            return self.send(403, {'error': 'PACE is available only on this computer.'})
        path = urlparse(self.path).path
        static = {'/': 'index.html', '/app.js': 'app.js', '/metrics.js': 'metrics.js', '/style.css': 'style.css', '/favicon.svg': 'favicon.svg', '/course.js': 'course.js', '/course-data.js': 'course-data.js', '/course-view.js': 'course-view.js', '/course.css': 'course.css', '/mission-inn-2026.jpg': 'mission-inn-2026.jpg'}
        if path in static:
            file = ROOT / 'static' / static[path]
            return self.send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or 'text/plain', session=path == '/')
        if not self.authorized():
            return self.send(401, {'error': 'Open PACE in this browser first.'})
        if path == '/api/state':
            return self.send(200, {'settings': self.server.db.settings(), 'runs': self.server.db.list(),
                                  'plans': self.server.db.list('plans'), 'sync': self.server.sync.snapshot(), 'csrf': self.server.csrf})
        if path == '/api/export':
            return self.send(200, {'format': 'PACE 1', 'exported_at': now(), 'settings': {k:v for k,v in self.server.db.settings().items() if k in DEFAULTS},
                                  'runs': self.server.db.list(), 'plans': self.server.db.list('plans')}, download='pace-backup.json')
        self.send(404, {'error': 'Not found.'})

    def do_POST(self):
        if not self.headers_safe() or not self.authorized() or not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), self.server.csrf):
            return self.send(403, {'error': 'Refresh PACE and try again.'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length <= 0 or length > 12_000_000:
                return self.send(413, {'error': 'Choose a file smaller than 8 MB.'})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Invalid request.')
            result = self.action(urlparse(self.path).path, body)
            self.send(200, result or {'ok': True})
        except (ValueError, TypeError, KeyError, ET.ParseError) as e:
            self.send(400, {'error': str(e)[:300]})
        except Exception as e:
            logging.error('Request failed (%s).', type(e).__name__)
            self.send(500, {'error': 'Something went wrong. Your saved data is safe; try again.'})

    def action(self, path, b):
        db, sync = self.server.db, self.server.sync
        if path == '/api/settings':
            updates = {}
            for k in ('runner_name', 'race_name', 'race_location'):
                if k in b:
                    updates[k] = str(b[k])[:150]
            if 'race_date' in b:
                updates['race_date'] = valid_date(b['race_date'])[:10] if b['race_date'] else None
            if 'race_url' in b:
                value = str(b['race_url'] or '').strip()
                parsed = urlparse(value)
                if value and (len(value) > 2000 or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password):
                    raise ValueError('Use a public HTTPS race website address.')
                updates['race_url'] = value
            if 'units' in b:
                if b['units'] not in ('mi', 'km'):
                    raise ValueError('Choose miles or kilometers.')
                updates['units'] = b['units']
            if 'goal_seconds' in b:
                updates['goal_seconds'] = number(b['goal_seconds'], 'Finish time in seconds', 1800, 36000, True)
            if 'weekly_target_m' in b:
                updates['weekly_target_m'] = number(b['weekly_target_m'], 'Weekly distance in meters', 1, 500000, True)
            if 'preview' in b:
                updates['preview'] = bool(b['preview'])
            if 'shoes' in b:
                if not isinstance(b['shoes'], list) or len(b['shoes']) > 30:
                    raise ValueError('Add up to 30 pairs of shoes.')
                updates['shoes'] = [{'id': str(s['id'])[:100], 'name': str(s['name'])[:100],
                                     'starting_m': number(s.get('starting_m', 0), 'Starting mileage', 0, 1e7)} for s in b['shoes']]
            db.save_settings(updates)
        elif path == '/api/garmin/login':
            email, password = str(b.get('email', '')).strip(), str(b.get('password', ''))
            if '@' not in email or not password or len(password) > 1000:
                raise ValueError('Enter your Garmin email and password.')
            sync.begin_login(email, password)
        elif path == '/api/garmin/mfa':
            code = str(b.get('code', '')).strip()
            if not code.isdigit() or not 4 <= len(code) <= 10:
                raise ValueError('Enter the verification code from Garmin.')
            sync.mfa(code)
        elif path == '/api/garmin/sync':
            sync.request_sync()
        elif path == '/api/garmin/disconnect':
            sync.disconnect()
        elif path == '/api/runs/save':
            old = db.get(str(b.get('id', '')))
            if old:
                if old['source'] == 'Garmin Connect':
                    allowed = {k: b[k] for k in ('kind', 'notes', 'rpe', 'shoe') if k in b}
                    r = {**old, **validate_run({**old, **allowed})}
                else:
                    r = {**old, **validate_run({**old, **b})}
            else:
                r = validate_run(b)
                r.update(id='manual:' + str(uuid.uuid4()), source='Manual entry')
            db.save(r)
            db.save_settings({'preview': False})
            return {'id': r['id']}
        elif path == '/api/import':
            raw = str(b.get('text', ''))
            if len(raw.encode()) > 8_000_000:
                raise ValueError('Choose a file smaller than 8 MB.')
            runs = import_file(str(b.get('filename', '')), raw, db.settings()['units'])
            count = sum(db.save(r, preserve=True) for r in runs)
            db.save_settings({'preview': False})
            return {'imported': count, 'duplicates': len(runs) - count}
        elif path == '/api/plans/save':
            date = valid_date(b.get('date'))[:10]
            kind = b.get('kind', 'Easy')
            if kind not in KINDS:
                raise ValueError('Choose a workout type.')
            id = str(b.get('id') or uuid.uuid4())[:100]
            plan = {'id': id, 'date': date, 'kind': kind, 'title': str(b.get('title') or kind)[:150],
                    'distance_m': number(b.get('distance_m'), 'Planned distance', 0, 1e6, True),
                    'notes': str(b.get('notes', ''))[:5000], 'done': bool(b.get('done', False))}
            db.save(plan, 'plans')
        elif path == '/api/plans/delete':
            db.delete(str(b['id']), 'plans')
        elif path == '/api/shutdown':
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            raise ValueError('Unknown action.')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    db = Database(DATA)
    sync = GarminSync(db)
    server = AppServer(('127.0.0.1', args.port), db, sync)
    threading.Thread(target=sync.loop, daemon=True).start()
    print(f'PACE is ready at http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()

if __name__ == '__main__':
    main()
