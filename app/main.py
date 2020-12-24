from fastapi import FastAPI

@app.get('/')
def read_root():
   return {"hello": "world!"}