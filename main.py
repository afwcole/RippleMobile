from fastapi import FastAPI, Header
from ussd import ussd_callback
from schemas import IncomingUSSDRequest
from dotenv import load_dotenv
from typing import Annotated
import sys

# Load variables from .env into the environment
load_dotenv()

sys.path.extend([".",".."])

app = FastAPI(docs_url="/")

@app.post("/incoming-ussd-request/")
def ussd_request(payload:IncomingUSSDRequest, sim: Annotated[bool | None, Header()] = False):
    return ussd_callback(payload, sim)