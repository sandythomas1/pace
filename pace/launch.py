"""Double-click Start PACE.cmd. No global packages or cloud services required."""
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser

root = Path(__file__).resolve().parent
url = 'http://127.0.0.1:8765'

def ready():
    try:
        with urllib.request.urlopen(url, timeout=2) as res:
            return b'PACE' in res.read(8000)
    except Exception:
        return False

def main():
    if ready():
        webbrowser.open(url)
        return
    runtime = root / '.venv' / 'Scripts' / 'python.exe'
    if not runtime.exists():
        print('Preparing PACE for this computer…')
        venv.create(root / '.venv', with_pip=True)
    required = (root / 'requirements-lock.txt').read_text(encoding='utf-8')
    check = "from importlib.metadata import version; import sys; pins=[line.strip().split('==') for line in sys.argv[1].splitlines() if line.strip() and not line.lstrip().startswith('#')]; sys.exit(0 if all(version(name)==wanted for name,wanted in pins) else 1)"
    result = subprocess.run([str(runtime), '-c', check, required], capture_output=True)
    if result.returncode:
        print('Installing the Garmin connector from the Python package registry…')
        subprocess.run([str(runtime), '-m', 'pip', 'install', '--disable-pip-version-check', '--retries', '1', '--timeout', '20', '--no-cache-dir', '-r', str(root / 'requirements-lock.txt')], check=True, timeout=240)
    logdir = root / '.data'
    logdir.mkdir(exist_ok=True)
    with (logdir / 'server.log').open('ab') as log:
        subprocess.Popen([str(runtime), str(root / 'server.py')], cwd=root, stdin=subprocess.DEVNULL,
                         stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(40):
        if ready():
            webbrowser.open(url)
            return
        time.sleep(.25)
    raise RuntimeError('PACE could not start. Check .data/server.log. Port 8765 may be in use.')

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Could not start PACE: {error}')
        sys.exit(1)
