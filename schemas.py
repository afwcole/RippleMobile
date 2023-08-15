from pydantic import BaseModel

class RegistrationRequest(BaseModel):
    phone_num: str
    name: str
    pin: str

class TransactionRequest(BaseModel):
    sender_phone_num: str
    recipient_phone_num: str
    amount_xrp: float
    pin: str

class IncomingUSSDRequest(BaseModel):
    USERID: str
    MSISDN: str
    USERDATA: str
    MSGTYPE: bool
    NETWORK: str
    SESSIONID: str

class USSDResponse(BaseModel):
    USERID: str
    MSISDN: str
    USERDATA: str
    MSG: str
    MSGTYPE: bool
