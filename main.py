from fastapi import FastAPI
from ussd import ussd_callback
from schemas import IncomingUSSDRequest
from dotenv import load_dotenv
import sys

# Load variables from .env into the environment
load_dotenv()

sys.path.extend([".",".."])

app = FastAPI()

@app.post("/incoming-ussd-request/")
def ussd_request(payload:IncomingUSSDRequest):
    return ussd_callback(payload)