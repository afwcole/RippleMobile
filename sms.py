import requests
from schemas import NaloSMSRequest

URL="https://sms.nalosolutions.com/smsbackend/Nal_resl/send-message/"
AUTH_KEY="2v2ne(o!ot(ret_0tkz6rz1#z13x5@@uf7vc(lz5p!0qilxq6he37nu@_lu5h7qw"
SENDER_ID="RippleMO"

def send_sms(message, recipient_phone_num):
    payload = NaloSMSRequest(
        key = AUTH_KEY, 
        msisdn = recipient_phone_num, 
        message = message,
        sender_id = SENDER_ID
    )
    
    response = requests.post(URL, json=payload.dict())

    if response.status_code == 200:
        result = response.json()
    else:
        print(f"Request failed with status code: {response.status_code}")