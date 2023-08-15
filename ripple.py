import xrpl
from xrpl import wallet, utils, transaction
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo
from xrpl.models.transactions import Payment
from schemas import RegistrationRequest, TransactionRequest
from utils import get_account_by_phone, save_to_json, load_data_from_json
from fastapi import HTTPException

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"
CLIENT = JsonRpcClient(JSON_RPC_URL)

def register_account(registration_request: RegistrationRequest):
    print(0)
    registration_dict = registration_request.dict()
    if get_account_by_phone(registration_dict['phone_num']):
        return "user already exists"
    
    print(1)
    
    try:
        new_wallet = wallet.generate_faucet_wallet(CLIENT)
        registration_dict['wallet_address'] = new_wallet.classic_address
        registration_dict['wallet_seed'] = new_wallet.seed
    except Exception as e:
        print(e)
        return "something went wrong, try again later"

    print(3)
    
    existing_accounts = load_data_from_json()
    print(4)
    existing_accounts.append(registration_dict)
    print(5)
    save_to_json(existing_accounts)
    print(6)

    
    return "account created"

def check_balance(phone_num: str, pin: str):
    user_account = get_account_by_phone(phone_num)
    if not user_account:
        return "User not found."

    if user_account['pin'] != pin:
        return "Incorrect PIN."
    
    try:
        acct_info = AccountInfo(account=user_account['wallet_address'], ledger_index="validated")
        response = CLIENT.request(acct_info)
        return f"you have {int(response.result['account_data']['Balance']) / 1_000_000} XRP"
    except xrpl.clients.exceptions.XrpClientException as e:
        print(e)
        return "something went wrong, try again later"

def send_xrp(transaction_request: TransactionRequest):
    sender = get_account_by_phone(transaction_request.sender_phone_num)
    recipient = get_account_by_phone(transaction_request.recipient_phone_num)
    
    if not sender:
        return "user not found"
    if not recipient:
        return "recipient does not have an account"
    if sender['pin'] != transaction_request.pin:
        return "incorrect pin"

    sending_wallet = wallet.Wallet.from_seed(sender['wallet_seed'])
    payment = Payment(
        account=sending_wallet.classic_address,
        amount=utils.xrp_to_drops(transaction_request.amount_xrp),
        destination=recipient['wallet_address']
    )
    
    try:
        signed_tx = transaction.autofill_and_sign(payment, CLIENT, sending_wallet)
        transaction.submit_and_wait(signed_tx, CLIENT)
        
        acct_info = AccountInfo(account=sending_wallet.classic_address, ledger_index="validated")
        response = CLIENT.request(acct_info)
        updated_balance = int(response.result['account_data']['Balance']) / 1_000_000
        return f"transaction successful, your new balance is {updated_balance}"
    except Exception as e:
        return "something went wrong, try again later"

def get_account_info(phone:str):
    account = get_account_by_phone(phone)
    if account:
        response = client.request(AccountInfo(
            account=account["wallet_address"],
            ledger_index="validated",
            strict=True,
        ))
        acct_info = response.result['account_data']
        return f"address: {acct_info.get('Account')} \n  balance: {acct_info.get('Balance')} \n sequence: {acct_info.get('Sequence')} \n index: {acct_info.get('index')}"
