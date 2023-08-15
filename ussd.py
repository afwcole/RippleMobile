from schemas import USSDResponse, IncomingUSSDRequest, RegistrationRequest, TransactionRequest
from ripple import get_account_info, get_transaction_history, register_account, check_balance, send_xrp
from utils import get_account_by_phone
from collections import defaultdict
import re

response = ''
PIN_PATTERN = r'^\d{4}$'
PHONE_PATTERN = r'^(233|0)\d{9}$'
AMOUNT = r'\$?\d+(?:\.\d{1,2})?'
sessions = defaultdict(lambda: defaultdict(dict))

def ussd_callback(payload:IncomingUSSDRequest):
    global response
    if payload.USERDATA == '*920*106':
        sessions[payload.SESSIONID]['stage'] = 0
        response = "Welcome to Ripple mobile \n"
        if get_account_by_phone(payload.MSISDN):
            response += "1. Check Wallet Balance \n"
            response += "2. Send XRP \n"
            response += "3. Get Account Info \n"
            response += "4. Get Transaction History \n"
            response += "5. Exit"
        else:
            response += "1. Register New Wallet \n"
            response += "2. Exit"

    # if user has an account
    elif get_account_by_phone(payload.MSISDN):
        # start page
        if payload.USERDATA == '1' or payload.USERDATA == '3' or payload.USERDATA == '4':
            sessions[payload.SESSIONID]['prev_choice'] = payload.USERDATA
            response = "Enter your 4 digit wallet pin"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # start page
        if payload.USERDATA == '2':
            response = "enter receipient phone number"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # validate pin and return balance
        elif re.match(PIN_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==1:
            prev_choice = sessions[payload.SESSIONID]['prev_choice']
            if prev_choice == "1":
                response = check_balance(payload.MSISDN, payload.USERDATA)
            elif prev_choice == "3":
                response = get_account_info(payload.MSISDN, payload.USERDATA)
            elif prev_choice == "4":
                response = get_transaction_history(payload.MSISDN, payload.USERDATA)
            payload.MSGTYPE = False
            del sessions[payload.SESSIONID]

        # validate phone number
        elif re.match(PHONE_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==1:
            response, payload.MSGTYPE = ("Enter amount", True) if get_account_by_phone(payload.USERDATA) else ("the receipient is not registered", False)
            sessions[payload.SESSIONID]['receipent_number'] = payload.USERDATA
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # validate amount
        elif re.match(AMOUNT, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==2:
            response = "Enter pin to send"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['amount'] = payload.USERDATA
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # validate pin and send amount
        elif re.match(PIN_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==3:
            response = send_xrp(
                TransactionRequest(
                    sender_phone_num=payload.MSISDN, 
                    recipient_phone_num=sessions[payload.SESSIONID]['receipent_number'], 
                    amount_xrp=sessions[payload.SESSIONID]['amount'], 
                    pin=payload.USERDATA, 
                )
            )
            payload.MSGTYPE = False
            del sessions[payload.SESSIONID]
        
        # exit
        if payload.USERDATA == '5':
            response = "Thank you for using our service, come back soon :)"
            payload.MSGTYPE = False

    elif payload.USERDATA == '1':
        response = "Enter your 4 digit wallet pin"
        payload.MSGTYPE = True

    # create ripple account
    elif re.match(PIN_PATTERN, payload.USERDATA):
        response = register_account(
            RegistrationRequest(   
                phone_num=payload.MSISDN,
                name=payload.MSISDN,
                pin=payload.USERDATA
            )
        )
        payload.MSGTYPE = False

    # exit
    elif payload.USERDATA == '2':
        response = "Thank you for using our service, come back soon :)"
        payload.MSGTYPE = False

    # invalid input
    else:
        response = "Invalid input"
        payload.MSGTYPE = False

    return USSDResponse(
        USERID = payload.USERID,
        MSISDN = payload.MSISDN,
        USERDATA = payload.USERDATA,
        MSG = response,
        MSGTYPE = payload.MSGTYPE
    )    
    