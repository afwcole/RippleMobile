import xrpl, os
from xrpl import wallet, utils, transaction
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo, AccountTx
from xrpl.models.transactions import Payment
from schemas import RegistrationRequest, TransactionRequest, SIMMessage
from utils import format_transactions, get_account_by_phone, save_to_json, load_data_from_json, encode
from dotenv import load_dotenv
from sms import send_sms
from storage import Account, Storage

load_dotenv()
db = Storage()

JSON_RPC_URL = os.environ.get('JSON_RPC_URL')
CLIENT = JsonRpcClient(JSON_RPC_URL)

def register_account(registration_request: RegistrationRequest, account_type:str, sim=False):
    sms, success = None, True
    message = f"Welcome to Ripple Mobile! \nYour {account_type.lower()} account was successfully created for phone number, {registration_request.phone_num}. \nDial *920*106# to start using Ripple Mobile."
    try:
        new_wallet = wallet.generate_faucet_wallet(CLIENT)
        db.add_account(Account(
            account_name=registration_request.name,
            account_type=account_type,
            pin=registration_request.pin,
            main_wallet=new_wallet,
            phone_number=registration_request.phone_num,
        ))
    except Exception as e:
        message, success = "Something went wrong, try again later", False    
    if not sim:
        send_sms(message, registration_request.phone_num)
    else:
        sms = [SIMMessage(
            TO=registration_request.phone_num,
            MESSAGE=message
        )]
    return success, sms

def check_balance(phone_num: str, pin: str, sim=False):
    user_account, sms = db.get_account(phone_num), None
    if not user_account:
        return "User not found.", sms
    
    if user_account.pin != encode(pin):
        return "Incorrect PIN.", sms
    
    try:
        acct_info = AccountInfo(account=user_account.main_wallet.classic_address, ledger_index="validated")
        response = CLIENT.request(acct_info)
        message = f"Current balance is {int(response.result['account_data']['Balance']) / 1_000_000} XRP"
        if not sim:
            send_sms(message, phone_num)
        else:
            sms = [
                SIMMessage(
                    TO=phone_num,
                    MESSAGE=message
                )
            ]
    except Exception as e:
        print(e)
        message = "Something went wrong, try again later"
    
    return message, sms
    
def get_balance(phone:str, ledger_index:str="validated"):
    account = db.get_account(phone)
    account = AccountInfo(account=account.main_wallet.classic_address, ledger_index="validated")
    account = CLIENT.request(account)
    return int(account.result['account_data']['Balance']) / 1_000_000

def send_xrp(transaction_request: TransactionRequest, sim=False):
    sms, response = None, ""
    user_account = db.get_account(transaction_request.sender_phone_num)
    recipient = db.get_account(transaction_request.recipient_phone_num)
    if not user_account:
        return "User not found.", sms
    if user_account.pin != transaction_request.pin:
        return "Incorrect PIN.", sms
    
    if transaction_request.amount_xrp >= get_balance(user_account.phone_number):
        return "You do not have enough funds to perform this operation.", sms
    
    sending_wallet = user_account.main_wallet
    receiving_wallat = recipient.main_wallet

    try:
        payment = Payment(
            account=sending_wallet.classic_address,
            amount=utils.xrp_to_drops(transaction_request.amount_xrp),
            destination=recipient.main_wallet.classic_address
        )
        
        signed_tx = transaction.autofill_and_sign(payment, CLIENT, sending_wallet)
        transaction.submit_and_wait(signed_tx, CLIENT)
        acct_info = AccountInfo(account=sending_wallet.classic_address, ledger_index="validated")
        recipient_acct_info = AccountInfo(account=receiving_wallat.classic_address, ledger_index="validated")
        sender_response = CLIENT.request(acct_info)
        recipient_response = CLIENT.request(recipient_acct_info)
        sender_updated_balance = int(sender_response.result['account_data']['Balance']) / 1_000_000
        recipient_updated_balance = int(recipient_response.result['account_data']['Balance']) / 1_000_000

        sender_message = f"Transaction successful, you sent {transaction_request.amount_xrp} XRP to {transaction_request.recipient_phone_num}, your Current Balance is {sender_updated_balance} XRP"
        recipient_message = f"You have received {transaction_request.amount_xrp} XRP from {transaction_request.sender_phone_num}, your Current Balance is {recipient_updated_balance} XRP"        

        if not sim:
            send_sms(sender_message, transaction_request.sender_phone_num)
            send_sms(recipient_message, transaction_request.recipient_phone_num)
        else:
            sms = [
                SIMMessage(TO=transaction_request.sender_phone_num, MESSAGE=sender_message),
                SIMMessage(TO=transaction_request.recipient_phone_num, MESSAGE=recipient_message)
            ]
        response = f"You have requested to send {transaction_request.amount_xrp} XRP to {transaction_request.recipient_phone_num}, we are processing your transaction request, you'll receive an sms when completed"
    except Exception as e:
        print(e)
        response = "Something went wrong, try again later"
        sms = [ SIMMessage(TO=transaction_request.sender_phone_num, MESSAGE=response) ]
        # return send_sms("Something went wrong, try again later", transaction_request.sender_phone_num)
    return response, sms

def get_account_info(phone:str, pin: str):
    user_account, response = db.get_account(phone), ""
    if not user_account:
        return "User not found."

    if user_account.pin != encode(pin):
        return "Incorrect PIN."
    
    try:
        if user_account:
            response = CLIENT.request(AccountInfo(
                account=user_account.main_wallet.classic_address,
                ledger_index="validated",
                strict=True,
            ))
            acct_info = response.result['account_data']
            response = f"Address: {acct_info.get('Account')} \nBalance: {int(acct_info.get('Balance')) / 1_000_000} XRP \nSequence: {acct_info.get('Sequence')} \nIndex: {acct_info.get('index')}"
        else:
            response = "No account found."
    except Exception as e:
        print(e)
        response = "Something went wrong, try again later"
    
    return response
    
def get_transaction_history(phone: str, pin: str, sim=False) -> str:
    user_account, sms, response = db.get_account(phone), None, ""
    
    if not user_account:
        return "User not found.", sms

    if user_account.pin != encode(pin):
        return "Incorrect PIN.", sms
    
    try:
        response = CLIENT.request(AccountTx(account=user_account.main_wallet.classic_address))
        transactions = response.result["transactions"]
        
        formatted_txn_msg = format_transactions(transactions)
        if not sim:
            send_sms(f"Transaction History Summary: \n{formatted_txn_msg}", phone)
        else:
            sms = [SIMMessage(
                    TO=phone,
                    MESSAGE=f"Transaction History Summary: \n{formatted_txn_msg}"
                )]
        response = f"Transaction history has been sent to {phone} via SMS"
    except Exception as e:
        print(e)
        response = "Something went wrong, try again later"
    
    return response, sms