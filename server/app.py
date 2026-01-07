from fastapi import FastAPI

from server.bootstrap import init_app

app = FastAPI(title="DevAll Workflow Server", version="1.0.0")
init_app(app)
