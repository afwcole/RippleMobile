from schemas import USSDResponse, IncomingUSSDRequest, RegistrationRequest, TransactionRequest
from ripple import get_account_info, get_transaction_history, register_account, check_balance, send_xrp, encode
from collections import defaultdict
from dotenv import get_key
from sms import send_sms
import re, threading, cachetools, random
from storage import Storage
from multisig import (
    register_multisig_account,
    request_multisig_tx,
    sign_multisig_tx,
    check_balance as mcb
)

response = ''
PIN_PATTERN = r'^\d{4}$'
POS_CODE_PATTERN = r'\*920\*106\*\d{3}$'
PHONE_PATTERN = r'^(233|0)\d{9}$'
NUMBER_OPTION_PATTERN=r'\b\d{1,2}\b'
AMOUNT = r'\$?\d+(?:\.\d{1,2})?'
sessions = defaultdict(lambda: defaultdict(dict))
cache = cachetools.TTLCache(maxsize=int(get_key('.env','MAX_CACHE_SIZE')), ttl=float(get_key('.env','CACHE_ITEM_TTL'))) 

def ussd_callback(payload:IncomingUSSDRequest):
    db = Storage()
    global response

    if re.match(POS_CODE_PATTERN, payload.USERDATA):
        sessions[payload.SESSIONID]['stage'] = 0
        sessions[payload.SESSIONID]['pr_session_key'] = payload.USERDATA[-3:]
        response = "Ripple mobile POS \n"
        if db.get_account(payload.MSISDN):
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
        account = db.get_account(payload.MSISDN)
        if account:
            response += "0.Approvals\n"
            response += "1.Wallet Balance\n"
            response += "2.Send XRP\n"
            response += "3.Account Info\n"
            response += "4.Transaction History\n"
            response += "5.Shared Wallet\n"
            if account.account_type=='MERCHANT':
                response += "6.Request Payment\n"
                response += "7.Exit"
            else:
                response += "6.Exit"
        else:
            response += "1. Register New Basic Wallet \n"
            response += "2. Register New Merchant Wallet \n"
            response += "3. Exit"

    # if user has an account
    elif db.get_account(payload.MSISDN):
        account = db.get_account(payload.MSISDN)
        
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
            if encode(payload.USERDATA) != account.pin:
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
        elif (payload.USERDATA == '0' or payload.USERDATA == '1' or payload.USERDATA == '3' or payload.USERDATA == '4') and sessions[payload.SESSIONID]['stage']==0:
            sessions[payload.SESSIONID]['prev_choice'] = payload.USERDATA
            response = "Enter your 4 digit wallet pin"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # send xrp
        if payload.USERDATA == '2' and sessions[payload.SESSIONID]['stage']==0:
            response = "enter receipient phone number"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # multisig menu
        if payload.USERDATA == '5' and sessions[payload.SESSIONID]['stage']==0:
            response = "Shared Account(Multi Signature)\n"
            response += "wallets owned by 2 or more people\n"
            response += "1. Shared Accounts\n"
            response += "2. Create Shared Account\n"
            sessions[payload.SESSIONID]['prev_choice']=payload.USERDATA
            sessions[payload.SESSIONID]['stage']+=10
            payload.MSGTYPE = True
            
        # Request payment thread for 5 for MERCHANT account_type
        if payload.USERDATA == '6' and account.account_type=='MERCHANT' and sessions[payload.SESSIONID]['stage']==0:
            response = "POS Request Payment\n" 
            response = "enter payment request amount"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1
            sessions[payload.SESSIONID]['prev_choice'] = payload.USERDATA

        # ask for pin for check account info multi sig
        elif sessions[payload.SESSIONID]['stage']==10 and sessions[payload.SESSIONID]['prev_choice']=="5" and payload.USERDATA=='1':
            response, payload.MSGTYPE = "Enter 4 digit pin", True

        # verify pin and get multi-sig wallets (list of shared accounts)
        elif sessions[payload.SESSIONID]['stage']==10 and sessions[payload.SESSIONID]['prev_choice']=="5" and re.match(PIN_PATTERN, payload.USERDATA):
            if account.pin == encode(payload.USERDATA):
                data = []
                for wallet in account.other_wallets:
                    data.append(db.get_multisig_account(wallet_addr=wallet))
                if data:       
                    response, payload.MSGTYPE = 'Your Shared Accounts(MultiSign)\n', True
                    response += '\n'.join([f"{idx}. {wallet.account_name}" for idx, wallet in enumerate(data)])
                    sessions[payload.SESSIONID]['stage']+=10
                    sessions[payload.SESSIONID]['ms-wallets']=data
                    sessions[payload.SESSIONID]['prev_choice']="5.1"
                else:
                    response, payload.MSGTYPE = "no multisign account created", False
            else:
                response, payload.MSGTYPE = "Invalid Pin", False

        # get multi-sig account menu
        elif sessions[payload.SESSIONID]['stage']==20 and sessions[payload.SESSIONID]['prev_choice']=="5.1"  and re.match(NUMBER_OPTION_PATTERN, payload.USERDATA):
            try:
                idx = int(payload.USERDATA)
                wallet = sessions[payload.SESSIONID]['ms-wallets'][idx]
            except:
                response, payload.MSGTYPE = "invalid input...", False
            else:
                # set wallet in session
                response = "Shared Account Menu\n"
                response += "1. Get Account Info\n"
                response += "2. Approvals\n"
                response += "3. Initiate Payment"
                sessions[payload.SESSIONID]['ms-wallet'] = wallet
                sessions[payload.SESSIONID]['stage']+=1
                payload.MSGTYPE = True

        # get multi-sig account info
        elif sessions[payload.SESSIONID]['stage']==21 and sessions[payload.SESSIONID]['prev_choice']=="5.1" and payload.USERDATA=='1':
            payload.MSGTYPE = False
            try:
                wallet = sessions[payload.SESSIONID]['ms-wallet']
            except:
                response = "invalid input..."
            else:
                response = 'Shared Account(MultiSign) Info\n'
                response += f'name: {wallet.account_name}\n'
                response += f'type: {wallet.account_type}\n'
                response += f'balance: {mcb(wallet.id, payload.MSISDN, account.pin)}'

        # get multi-sig account approvals
        elif sessions[payload.SESSIONID]['stage']==21 and sessions[payload.SESSIONID]['prev_choice']=="5.1" and payload.USERDATA=='2':
            response = "Approval List"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['stage']+=5
            # response will be open approvals

        # select multi-sig account approval to sign
        elif sessions[payload.SESSIONID]['stage']==26 and sessions[payload.SESSIONID]['prev_choice']=="5.1" and re.match(NUMBER_OPTION_PATTERN, payload.USERDATA):
            response, payload.MSGTYPE = "Enter your 4 digit pin", True
            sessions[payload.SESSIONID]['stage']+=1
            # ask for pin to validate approval
            # response will be open approvals

        # validate multi-sig account approval pin and sign
        elif sessions[payload.SESSIONID]['stage']==27 and sessions[payload.SESSIONID]['prev_choice']=="5.1" and re.match(PIN_PATTERN, payload.USERDATA):
            response, payload.MSGTYPE = "You have requested to sign this transaction, you will be notified when complete", False
            # ask for pin to validate approval

        #multi-sig account request payment receipient number
        elif sessions[payload.SESSIONID]['stage']==21 and sessions[payload.SESSIONID]['prev_choice']=="5.1" and payload.USERDATA=='3':
            response, payload.MSGTYPE = "Enter receipient phone number", True
            sessions[payload.SESSIONID]['stage']+=1

        #  multi-sig account request payment amount 
        elif sessions[payload.SESSIONID]['stage']==22 and sessions[payload.SESSIONID]['prev_choice']=="5.1" and re.match(PHONE_PATTERN, payload.USERDATA):
            response, payload.MSGTYPE = "Enter amount of XRP you want to send", True
            sessions[payload.SESSIONID]['receipent_number']=payload.USERDATA
            sessions[payload.SESSIONID]['stage']+=1
            
        # multi-sig account request payment amount
        elif sessions[payload.SESSIONID]['stage']==23 and sessions[payload.SESSIONID]['prev_choice']=="5.1" and re.match(AMOUNT, payload.USERDATA):
            # validate account amount -> wallet = sessions[payload.SESSIONID]['ms-wallet']
            sessions[payload.SESSIONID]['amount'] = payload.USERDATA
            response, payload.MSGTYPE = "Enter your 4 digit pin", True
            sessions[payload.SESSIONID]['stage']+=1

        # multi-sig account create payment request
        elif sessions[payload.SESSIONID]['stage']==24 and sessions[payload.SESSIONID]['prev_choice']=="5.1" and re.match(PIN_PATTERN, payload.USERDATA):
            payload.MSGTYPE = False
            if account.pin != encode(payload.USERDATA):
                response = "Incorrect pin."
            else:
                wallet = sessions[payload.SESSIONID]['ms-wallet']
                transaction_request = TransactionRequest(
                    sender_phone_num=payload.MSISDN,
                    recipient_phone_num=sessions[payload.SESSIONID]['receipent_number'],
                    amount_xrp=sessions[payload.SESSIONID]['amount'] ,
                    pin=payload.USERDATA
                )
                threading.Thread(target=request_multisig_tx, args=(wallet.id, transaction_request)).start()
                response = "We are creating your payment request"

        # set account name in session for multi-sig
        elif sessions[payload.SESSIONID]['stage']==10 and sessions[payload.SESSIONID]['prev_choice']=="5" and payload.USERDATA=='2':
            response = "Create Shared Account\n"
            response += "enter multi-signature account name"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['multi-sig'] = {
                "account_name": str(),
                "min_signers": int(),
                "signers": {payload.MSISDN},
            }
            sessions[payload.SESSIONID]['stage']+=1
   
        # ask multi-sig signers menu
        elif sessions[payload.SESSIONID]['stage']==11 and sessions[payload.SESSIONID]['prev_choice']=="5":
            response = "Add Shared Account Signers\n"
            response+="enter phone number\n"
            sessions[payload.SESSIONID]['multi-sig']['account_name'] = payload.USERDATA
            sessions[payload.SESSIONID]['stage']+=1
            payload.MSGTYPE = True

        # multi-sig recurring phone number ask and save phone number
        elif sessions[payload.SESSIONID]['stage']==12 and sessions[payload.SESSIONID]['prev_choice']=="5" and re.match(PHONE_PATTERN, payload.USERDATA):

            if not db.get_account(payload.USERDATA):
                response, payload.MSGTYPE = "the signer number is not registered", False
            
            elif payload.MSISDN==payload.USERDATA:
                response, payload.MSGTYPE = "you are already a signer...", False

            else:
                response = "Create Shared Account\n"
                response += "1. Add another signer\n"
                response += "2. Done\n"
                sessions[payload.SESSIONID]['multi-sig']['signers'].add(payload.USERDATA)
                sessions[payload.SESSIONID]['stage']+=1
                payload.MSGTYPE = True

        # multi-sig recurring phone number
        elif sessions[payload.SESSIONID]['stage']==13 and sessions[payload.SESSIONID]['prev_choice']=="5":
            response="Add Shared Account Signers\n"
            response+="enter phone number\n"

            payload.MSGTYPE=True

            if payload.USERDATA == "1":
                sessions[payload.SESSIONID]['stage']-=1
            elif payload.USERDATA =="2":
                sessions[payload.SESSIONID]['stage']+=1
                response = "Set minimun number of signers\n"
                response+="enter number\n"
            else:
                response, payload.MSGTYPE = "invalid input...", False

        # validate and set min signer count
        elif sessions[payload.SESSIONID]['stage']==14 and sessions[payload.SESSIONID]['prev_choice']=="5":
            try:
                count = int(payload.USERDATA)
            except:
                response, payload.MSGTYPE="invalid input...\n", False
            else: 
                if count > len(sessions[payload.SESSIONID]['multi-sig']['signers']):
                    response, payload.MSGTYPE="minimum number of signers specified is more than available signers\n", False
                else:
                    response="Enter pin to create shared wallet\n"
                    sessions[payload.SESSIONID]['multi-sig']['min_signers'] = count
                    sessions[payload.SESSIONID]['stage']+=1
                    payload.MSGTYPE=True

        #  create multisign account
        elif sessions[payload.SESSIONID]['stage']==15 and sessions[payload.SESSIONID]['prev_choice']=="5" and re.match(PIN_PATTERN, payload.USERDATA):
            sesh = sessions[payload.SESSIONID]['multi-sig']
            threading.Thread(target=register_multisig_account, kwargs={
                'account_name':sesh['account_name'],
                'min_num_signers':sesh['min_signers'],
                'signer_phone_nums':list(sesh['signers']),
                'msidn':payload.MSISDN,
                'pin':payload.USERDATA,
            }).start()

            response = f"We are creating your shared(multi-sig) account - {sesh['account_name']}. you and other signers will be notified via SMS when complete."
            payload.MSGTYPE=False
            del sessions[payload.SESSIONID]
        
        # validate pin for My Approvals
        elif re.match(PIN_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==1 and sessions[payload.SESSIONID]['prev_choice']=="0":

            if encode(payload.USERDATA) != account.pin:
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
            response, payload.MSGTYPE = ("Enter amount", True) if db.get_account(payload.USERDATA) else ("the receipient is not registered", False)
            sessions[payload.SESSIONID]['receipent_number'] = payload.USERDATA
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # validate phone number for POS
        elif re.match(PHONE_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==2 and account.account_type=='MERCHANT':
            response, payload.MSGTYPE = "Enter pin", True
            # if send send reject
            if payload.USERDATA == payload.MSISDN:
                response, payload.MSGTYPE = '', False

            if not db.get_account(payload.USERDATA):
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
        elif re.match(AMOUNT, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==1 and sessions[payload.SESSIONID]['prev_choice']=='6':
            response = "Enter payee phone number"
            payload.MSGTYPE = True
            sessions[payload.SESSIONID]['amount'] = payload.USERDATA
            sessions[payload.SESSIONID]['stage']=sessions[payload.SESSIONID]['stage']+1

        # validate pin for POS request Payment
        elif re.match(PIN_PATTERN, payload.USERDATA) and sessions[payload.SESSIONID]['stage']==3 and sessions[payload.SESSIONID]['prev_choice']=='6':
            payee = db.get_account(sessions[payload.SESSIONID]['receipent_number'])

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
            
            sender = db.get_account(payload.MSISDN)
            recipient = db.get_account(sessions[payload.SESSIONID]['receipent_number'])

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

            payee = db.get_account(payload.MSISDN)
            requester = db.get_account(session['requester'])

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
        if payload.USERDATA == '7' or all((payload.USERDATA == '6', account.account_type=='BASIC')):
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
        if db.get_account(payload.MSISDN):
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
    