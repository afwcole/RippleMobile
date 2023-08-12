import json
import xrpl
from typing import Union, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from xrpl import wallet, utils, transaction
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo
from xrpl.models.transactions import Payment

app = FastAPI()

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"
CLIENT = JsonRpcClient(JSON_RPC_URL)

class RegistrationRequest(BaseModel):
    phone_num: str
    name: str
    pin: str

class TransactionRequest(BaseModel):
    sender_phone_num: str
    recipient_phone_num: str
    amount_xrp: float
    pin: str

@app.post("/account/register")
def register_account(registration_request: RegistrationRequest):
    registration_dict = registration_request.dict()
    if get_account_by_phone(registration_dict['phone_num']):
        raise HTTPException(status_code=400, detail="A record with this phone number already exists.")
    
    try:
        new_wallet = wallet.generate_faucet_wallet(CLIENT)
        registration_dict['wallet_address'] = new_wallet.classic_address
        registration_dict['wallet_seed'] = new_wallet.seed
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate wallet: {str(e)}")
    
    existing_accounts = load_data_from_json()
    existing_accounts.append(registration_dict)
    save_to_json(existing_accounts)
    
    return {"status": "success"}

@app.get("/account/balance/{phone_num}/{pin}")
def check_balance(phone_num: str, pin: str):
    user_account = get_account_by_phone(phone_num)
    if not user_account:
        raise HTTPException(status_code=404, detail="User not found.")
    if user_account['pin'] != pin:
        raise HTTPException(status_code=401, detail="Incorrect PIN.")
    
    try:
        acct_info = AccountInfo(account=user_account['wallet_address'], ledger_index="validated")
        response = CLIENT.request(acct_info)
        return {"balance": int(response.result['account_data']['Balance']) / 1_000_000}
    except xrpl.clients.exceptions.XrpClientException as e:
        raise HTTPException(status_code=500, detail="Failed to communicate with the XRPL.")

@app.post("/transact/")
def send_xrp(transaction_request: TransactionRequest):
    sender = get_account_by_phone(transaction_request.sender_phone_num)
    recipient = get_account_by_phone(transaction_request.recipient_phone_num)
    
    if not sender or not recipient:
        raise HTTPException(status_code=404, detail="One of the users does not exist.")
    if sender['pin'] != transaction_request.pin:
        raise HTTPException(status_code=401, detail="Incorrect PIN.")

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
        return {"status": "success", "updated_balance": updated_balance}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_account_by_phone(phone_num: str) -> Union[dict, None]:
    accounts = load_data_from_json()
    return next((acc for acc in accounts if acc['phone_num'] == phone_num), None)

def load_data_from_json(filename="data.json") -> List[dict]:
    try:
        with open(filename, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_to_json(data: List[dict], filename="data.json"):
    with open(filename, "w") as file:
        json.dump(data, file)