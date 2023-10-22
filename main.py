from fastapi.middleware.cors import CORSMiddleware
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

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/incoming-ussd-request/")
def ussd_request(payload:IncomingUSSDRequest, sim: Annotated[bool | None, Header()] = False):
    return ussd_callback(payload, sim)