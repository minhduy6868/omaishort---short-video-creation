from __future__ import annotations

from bootstrap import ensure_sys_path

ensure_sys_path()

import uvicorn
from omaishort.config import API_HOST, API_PORT

if __name__ == "__main__":
    uvicorn.run("omaishort.main:app", host=API_HOST, port=API_PORT, reload=False)
