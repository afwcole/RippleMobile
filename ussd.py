from schemas import USSDResponse, IncomingUSSDRequest, RegistrationRequest, TransactionRequest
from ripple import get_account_info, get_transaction_history, register_account, check_balance, send_xrp, encode
from utils import get_account_by_phone
from collections import defaultdict
from dotenv import get_key
from sms import send_sms
import re, threading, cachetools, random

response = ''
PIN_PATTERN = r'^\d{4}$'
POS_CODE_PATTERN = r'\*920\*106\*\d{3}$'
PHONE_PATTERN = r'^(233|0)\d{9}$'
NUMBER_OPTION_PATTERN=r'\b\d{1,2}\b'
AMOUNT = r'\$?\d+(?:\.\d{1,2})?'
sessions = defaultdict(lambda: defaultdict(dict))
cache = cachetools.TTLCache(maxsize=int(get_key('.env','MAX_CACHE_SIZE')), ttl=float(get_key('.env','CACHE_ITEM_TTL'))) 

def ussd_callback(payload:IncomingUSSDRequest):
    global response

    if re.match(POS_CODE_PATTERN, payload.USERDATA):
        sessions[payload.SESSIONID]['stage'] = 0
        sessions[payload.SESSIONID]['pr_session_key'] = payload.USERDATA[-3:]
        response = "Ripple mobile POS \n"
        if get_account_by_phone(payload.MSISDN):
            request_info = cache.get(payload.USERDATA[-3:])
            if not request_info:
                response = "Payment request session expired"
            elif request_info['payee'] != payload.MSISDN:
                response = "Invalid operation, payment request was not assigned to your account"
            else:
                response += f"Enter pin to approve payment {request_info['amount']} XRP from {request_info['requester']}\n"
        else:
            response += f"You do not have a wallet with use, enter 0 to create one now\n"

    elif payload.USERDATA == '*920*106':
        sessions[payload.SESSIONID]['stage'] = 0
        response = "Welcome to Ripple mobile \n"
        account = get_account_by_phone(payload.MSISDN)
        if account:
            response += "0. My Approvals \n"
            response += "1. Check Wallet Balance \n"
            response += "2. Send XRP \n"
            response += "3. Get Account Info \n"
            response += "4. Get Transaction History \n"
            if account['account_type']=='MERCHANT':
                response += "5. Request Payment\n"
                response += "6. Exit"
            else:
                response += "5. Exit"
        else:
            response += "1. Register New Basic Wallet \n"
            response += "2. Register New Merchant Wallet \n"
            response += "3. Exit"

    # if user has an account
    elif get_account_by_phone(payload.MSISDN):
        account = get_account_by_phone(payload.MSISDN)
        
        if sessions[payload.SESSIONID]['stage']==7 and re.match(NUMBER_OPTION_PATTERN, payload.USERDATA):

            approval = sessions[payload.SESSIONID]['approvals'].get(payload.USERDATA)
            if not approval:
                response, payload.MSGTYPE = 'invalid input...', False
            else:
                sessions[payload.SESSIONID]['amount']=approval['amount'] 
                sessions[payload.SESSIONID]['receipent_number']=approval['requester'] 
                response, payload.MSGTYPE = 'Enter your 4 digit wallet pin', True
                sessions[payload.SESSIONID]['stage']+=1

        # pin for my approvals
        elif re.match(PIN_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==8:
            if encode(payload.USERDATA) != account.get('pin'):
                response, payload.MSGTYPE = "Incorrect PIN.", False
            else:
                approvals = sessions[payload.SESSIONID]['approvals']
                data = TransactionRequest(
                    sender_phone_num=payload.MSISDN, 
                    recipient_phone_num=sessions[payload.SESSIONID]['receipent_number'], 
                    amount_xrp=sessions[payload.SESSIONID]['amount'], 
                    pin=payload.USERDATA, 
                )
                response = f"You have requested to send {sessions[payload.SESSIONID]['amount']} XRP to {sessions[payload.SESSIONID]['receipent_number']}, we are processing your transaction request, you'll receive an sms when completed"
                threading.Thread(target=send_xrp, args=(data,)).start()
            payload.MSGTYPE = False

            # get chache key
            keys = [k for k,v in cache.items() 
                        if v['amount']==sessions[payload.SESSIONID]['amount'] 
                            and v['payee']==payload.MSISDN
                                and v['requester']==sessions[payload.SESSIONID]['receipent_number']]
            if keys:
                cache.pop(keys[0])
            del sessions[payload.SESSIONID]

        # start page
        elif payload.USERDATA == '0' or payload.USERDATA == '1' or payload.USERDATA == '3' or payload.USERDATA == '4':
            sessions[payload.SESSIONID]['prev_choice'] = payload.USERDATA
            response = "Enter your 4 digit wallet pin"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # start page
        if payload.USERDATA == '2' and sessions[payload.SESSIONID]['stage']==0:
            response = "enter receipient phone number"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # Request payment thread for 5 for MERCHANT account_type
        if payload.USERDATA == '5' and account['account_type']=='MERCHANT' and sessions[payload.SESSIONID]['stage']==0:
            response = "POS Request Payment\n" 
            response = "enter payment request amount"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1
            sessions[payload.SESSIONID]['prev_choice'] = payload.USERDATA

        # validate pin for My Approvals
        elif re.match(PIN_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==1 and sessions[payload.SESSIONID]['prev_choice']=="0":

            if encode(payload.USERDATA) != account.get('pin'):
                response, payload.MSGTYPE = "Incorrect PIN.", False
            else:
                sessions[payload.SESSIONID]['approvals'] = {}
                response, payload.MSGTYPE,  = "My Approvals\n", True
                response += 'select any approval to confirm\n'
                approvals = [v for k,v in cache.items() if cache.get(k,{}).get('payee')==payload.MSISDN]
                if not approvals:
                    response += "no pending approvals..."
                    payload.MSGTYPE = False
                else:
                    for idx,d in enumerate(approvals):
                        sessions[payload.SESSIONID]['approvals'][str(idx+1)] = d
                        response += f"{idx+1}. {d['amount']} XRP requested by {d['requester']}\n"

                sessions[payload.SESSIONID]['stage']+=6

        # validate pin and return balance
        elif re.match(PIN_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==1:
            prev_choice = sessions[payload.SESSIONID]['prev_choice']
            if prev_choice == "1":
                response = check_balance(payload.MSISDN, payload.USERDATA)
            elif prev_choice == "3":
                response = get_account_info(payload.MSISDN, payload.USERDATA)
            elif prev_choice == "4":
                threading.Thread(target=get_transaction_history, args=(payload.MSISDN, payload.USERDATA)).start()
                response = "We're preparing your history, we'll send an sms once it's ready"
            payload.MSGTYPE = False
            del sessions[payload.SESSIONID]

        # validate phone number
        elif re.match(PHONE_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==1:
            response, payload.MSGTYPE = ("Enter amount", True) if get_account_by_phone(payload.USERDATA) else ("the receipient is not registered", False)
            sessions[payload.SESSIONID]['receipent_number'] = payload.USERDATA
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # validate phone number for POS
        elif re.match(PHONE_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==2 and account['account_type']=='MERCHANT':
            response, payload.MSGTYPE = "Enter pin", True
            # if send send reject
            if payload.USERDATA == payload.MSISDN:
                response, payload.MSGTYPE = '', False

            if not get_account_by_phone(payload.USERDATA):
                response, payload.MSGTYPE = "the receipient is not registered", False

            sessions[payload.SESSIONID]['receipent_number'] = payload.USERDATA
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # validate amount
        elif re.match(AMOUNT, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==2:
            response = "Enter pin to send"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['amount'] = payload.USERDATA
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # validate amount for POS
        elif re.match(AMOUNT, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==1 and sessions[payload.SESSIONID]['prev_choice']=='5':
            response = "Enter payee phone number"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['amount'] = payload.USERDATA
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # validate pin for POS request Payment
        elif re.match(PIN_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==3 and sessions[payload.SESSIONID]['prev_choice']=='5':
            payee = get_account_by_phone(sessions[payload.SESSIONID]['receipent_number'])

            if not payee:
                response = "payee account not found"

            code = str(random.randint(100, 999))

            cache[code] = {
                'amount':sessions[payload.SESSIONID]['amount'],
                'payee':sessions[payload.SESSIONID]['receipent_number'],
                'requester':payload.MSISDN
            }  

            message = f'Payment request from Merchant with phone {payload.MSISDN} to pay {sessions[payload.SESSIONID]["amount"]} XRP\n'
            message += f'Dial *920*106*{code}# to approve payment of {sessions[payload.SESSIONID]["amount"]} to Merchant {payload.MSISDN}\n'
            message += 'Ignore if you are not aware of this transaction.'
            threading.Thread(target=send_sms, args=(message, sessions[payload.SESSIONID]['receipent_number'])).start()
            response = "payment request initiated"

        # validate pin and send amount
        elif re.match(PIN_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==3:
            
            sender = get_account_by_phone(payload.MSISDN)
            recipient = get_account_by_phone(sessions[payload.SESSIONID]['receipent_number'])

            if not sender:
                response = "sender account not found"

            elif not recipient:
                response = "recipient account not found"

            else:
                data = TransactionRequest(
                    sender_phone_num=payload.MSISDN, 
                    recipient_phone_num=sessions[payload.SESSIONID]['receipent_number'], 
                    amount_xrp=sessions[payload.SESSIONID]['amount'], 
                    pin=payload.USERDATA, 
                )
                response = f"You have requested to send {sessions[payload.SESSIONID]['amount']} XRP to {sessions[payload.SESSIONID]['receipent_number']}, we are processing your transaction request, you'll receive an sms when completed"
                threading.Thread(target=send_xrp, args=(data,)).start()
            payload.MSGTYPE = False
            del sessions[payload.SESSIONID]

        # validate pin and approve payment request
        elif re.match(PIN_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==0 and sessions[payload.SESSIONID]['pr_session_key']:
            key = sessions[payload.SESSIONID]['pr_session_key']
            session = cache.get(key)

            if not session:
                response = "Payment request session expired"

            payee = get_account_by_phone(payload.MSISDN)
            requester = get_account_by_phone(session['requester'])

            if not payee:
                response = "payee account not found"

            elif not requester:
                response = "requester account not found"

            else:
                data = TransactionRequest(
                    sender_phone_num=payee['phone_num'], 
                    recipient_phone_num=requester['phone_num'], 
                    amount_xrp=session['amount'], 
                    pin=payload.USERDATA, 
                )
                response = f"You have approved payment request to send {session['amount']} XRP to {requester['phone_num']}, we are processing your transaction request, you'll receive an sms when completed"
                threading.Thread(target=send_xrp, args=(data,)).start()

            payload.MSGTYPE = False
            if key in session:
                del session[key]

        # exit
        if payload.USERDATA == '6' or all((payload.USERDATA == '5', account['account_type']=='BASIC')):
            response = "Thank you for using our service, come back soon :)"
            payload.MSGTYPE = False
        

    elif payload.USERDATA == '0':
        response += "1. Register New Basic Wallet \n"
        response += "2. Register New Merchant Wallet \n"
        response += "3. Exit"
        payload.MSGTYPE = True

    elif payload.USERDATA in ['1', '2']:
        sessions[payload.SESSIONID]['prev_choice'] = payload.USERDATA
        response = "Enter your 4 digit wallet pin"
        payload.MSGTYPE = True

    # create ripple account
    elif re.match(PIN_PATTERN, payload.USERDATA):
        if get_account_by_phone(payload.MSISDN):
            response = "You already have an account with us"
        else:
            account_type = 'MERCHANT' if sessions[payload.SESSIONID]['prev_choice'] == '2' else 'BASIC'
            response = "We are creating your account, you'll receive an sms when it is completed"
            data = RegistrationRequest(   
                phone_num=payload.MSISDN,
                name=payload.MSISDN,
                pin=payload.USERDATA
            )
            threading.Thread(target=register_account, args=(data, account_type)).start()
        payload.MSGTYPE = False

    # exit
    elif payload.USERDATA == '3':
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
    