from fastapi import FastAPI
import peewee as pw

app = FastAPI()

@app.get('/')
def read_root():
    return {"hello": "world! this file is changed. again."}
