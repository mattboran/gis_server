from fastapi import FastAPI
from peewee import SqliteDatabase

app = FastAPI()

db = SqliteDatabase('database.db', pragmas={
    'journal_mode': 'wal',
    'cache_size': -1024 * 64
})

@app.get('/')
def read_root():
    return {"hello": "world! this file is changed. again."}
