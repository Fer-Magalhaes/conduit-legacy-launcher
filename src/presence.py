# Discord Rich Presence over the Discord client's local IPC pipe (no extra libraries). Shows the game's
# name under RPCS3's own Discord app; no game images are used.
import ctypes, json, os, struct, threading, time, uuid

CLIENT_ID = '424004941485572097'  # RPCS3's Discord app


def _watcher_running():
    # E:\psports\discord-presence already shows these games when it runs
    h = ctypes.windll.kernel32.OpenMutexW(0x00100000, False, 'Local\\infamous_discord_presence')
    if h:
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    return False


class _Pipe:
    def __init__(self):
        self.f = None
        for i in range(10):
            try:
                self.f = open(rf'\\.\pipe\discord-ipc-{i}', 'r+b', buffering=0)
                break
            except OSError:
                pass
        if not self.f:
            raise OSError('Discord not running')

    def send(self, op, data):
        body = json.dumps(data).encode()
        self.f.write(struct.pack('<II', op, len(body)) + body)

    def recv(self):
        op, n = struct.unpack('<II', self.f.read(8))
        return json.loads(self.f.read(n))


class Presence:
    """Shows "Jogando <game>" while the game runs; retries if Discord starts later."""

    def __init__(self, key, name, state):
        self.act = {
            'details': name, 'state': state, 'type': 0, 'status_display_type': 2,
            'timestamps': {'start': int(time.time())},
        }
        self.stop = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        if _watcher_running():
            return
        pipe = None
        while not self.stop.is_set():
            if not pipe:
                try:
                    pipe = _Pipe()
                    pipe.send(0, {'v': 1, 'client_id': CLIENT_ID})
                    pipe.recv()
                    pipe.send(1, {'cmd': 'SET_ACTIVITY', 'args': {'pid': os.getpid(), 'activity': self.act},
                                  'nonce': str(uuid.uuid4())})
                    pipe.recv()
                except (OSError, struct.error, ValueError):
                    pipe = None
            self.stop.wait(15)
        if pipe:
            try:
                pipe.f.close()
            except OSError:
                pass

    def close(self):
        self.stop.set()
