from pydantic import BaseModel, validator
from utils import encode
import re

def validate_pin_and_encode(cls, v: str) -> str:
    if not re.match(r'^\d{4}$', v):
        raise ValueError('pin must be contain 4 digits')            
    return validate_encoded_string(v)

class RegistrationRequest(BaseModel):
    phone_num: str
    name: str
    pin: str

    _validate_pin_and_encode = validator("pin", allow_reuse=True)(encode)

class TransactionRequest(BaseModel):
    sender_phone_num: str
    recipient_phone_num: str
    amount_xrp: float
    pin: str

    _validate_pin_and_encode = validator("pin", allow_reuse=True)(encode)

class IncomingUSSDRequest(BaseModel):
    USERID: str
    MSISDN: str
    USERDATA: str
    MSGTYPE: bool
    NETWORK: str
    SESSIONID: str

class SIMMessage(BaseModel):
    TO: str
    MESSAGE: str

class USSDResponse(BaseModel):
    USERID: str
    MSISDN: str
    USERDATA: str
    MSG: str
    MSGTYPE: bool
    SIM_MESSAGE: SIMMessage = None

class NaloSMSRequest(BaseModel):
    key: str
    msisdn: str
    message: str
    sender_id: str
