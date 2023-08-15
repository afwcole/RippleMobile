from schemas import USSDResponse, IncomingUSSDRequest, RegistrationRequest, TransactionRequest
from ripple import register_account, check_balance, send_xrp
from utils import get_account_by_phone
from collections import defaultdict
from fastapi import BackgroundTasks
import re, threading

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
            response += "3. Exit"
        else:
            response += "1. Register New Wallet \n"
            response += "2. Exit"

    # if user has an account
    elif get_account_by_phone(payload.MSISDN):
        # start page
        if payload.USERDATA == '1':
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
            response = check_balance(payload.MSISDN, payload.USERDATA)
            payload.MSGTYPE = False
            del sessions[payload.SESSIONID]

        # validate phone number
        elif re.match(PHONE_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==1:
            # sessions[payload.SESSIONID]['receipent_number'] = 
            response, payload.MSGTYPE = ("Enter amount", True) if get_account_by_phone(payload.USERDATA) else ("the receipient is not registered", False)
            if payload.USERDATA.startswith("0") and payload.MSISDN.startswith("233"):
                payload.USERDATA = payload.MSISDN[:3]+payload.USERDATA[1:]
            if payload.MSISDN == payload.USERDATA:
                response, payload.MSGTYPE = ("you cannot send funds to yourself", True)
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
            sender = get_account_by_phone(payload.MSISDN)
            recipient = get_account_by_phone(sessions[payload.SESSIONID]['receipent_number'])
            if not sender:
                response = "sender account not found"
            elif not recipient:
                response = "recipient account not found"
            elif sender['pin'] != payload.USERDATA:
                response = "incorrect pin"
            else:            
                data = TransactionRequest(
                    sender_phone_num=payload.MSISDN, 
                    recipient_phone_num=sessions[payload.SESSIONID]['receipent_number'], 
                    amount_xrp=float(sessions[payload.SESSIONID]['amount']), 
                    pin=payload.USERDATA, 
                )
                threading.Thread(target=send_xrp, args=(data,)).start()
                response = "processing transaction, you will receive an sms once we're done"
            payload.MSGTYPE = False
            del sessions[payload.SESSIONID]
        
        # exit
        if payload.USERDATA == '3':
            response = "Thank you for using our service, come back soon :)"
            payload.MSGTYPE = False

    elif payload.USERDATA == '1':
        response = "Enter your 4 digit wallet pin"
        payload.MSGTYPE = True

    # create ripple account
    elif re.match(PIN_PATTERN, payload.USERDATA):     
        if get_account_by_phone(payload.MSISDN): 
            response = "user already exists"
        else:
            data = RegistrationRequest(phone_num=payload.MSISDN, name=payload.MSISDN, pin=payload.USERDATA)
            threading.Thread(target=register_account, args=(data,)).start()
            response = "account is being created, you will receive an sms when account has been created"
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
    