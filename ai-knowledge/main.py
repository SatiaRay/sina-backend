from typing import Union

from fastapi import FastAPI

app = FastAPI()


@app.get("/test")
def test():
    return {"msg": "The service is up !"}