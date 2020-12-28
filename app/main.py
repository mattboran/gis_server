from fastapi import FastAPI
from api.api import router

app = FastAPI(title="GIS Locator")

app.include_router(router)
