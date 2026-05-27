import os

import uvicorn

from app import create_app


HOST = os.getenv("M2614_HOST", "0.0.0.0")
PORT = int(os.getenv("M2614_PORT", "8000"))

app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
