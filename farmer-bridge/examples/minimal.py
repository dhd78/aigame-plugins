# Minimal example: write to the main code page and run it.

import json
import urllib.request

BASE = "http://127.0.0.1:15800"


def api(path, method="GET", body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    print(api("/health"))
    print(api("/state"))
    print(api("/code", "POST", {"file": "main", "source": "do_a_flip()"}))
    print(api("/run", "POST", {"file": "main"}))
