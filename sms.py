import requests, os
from schemas import NaloSMSRequest
from dotenv import load_dotenv

load_dotenv()

URL=os.environ.get('SMS_URL')
AUTH_KEY=os.environ.get('SMS_AUTH_KEY')
SENDER_ID=os.environ.get('SMS_SENDER_ID')

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
        # log here
        print("sms request sent")
    else:
        print(f"Request failed with status code: {response.status_code}")