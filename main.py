from fastapi import FastAPI
from ussd import ussd_callback
from schemas import IncomingUSSDRequest
import sys

sys.path.extend([".",".."])

app = FastAPI()

@app.post("/incoming-ussd-request/")
def ussd_request(payload:IncomingUSSDRequest):
    return ussd_callback(payload)