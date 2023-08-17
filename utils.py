from datetime import datetime
import json, hashlib
from pydoc import text
from typing import Union, List

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

def encode(data:str):
    return hashlib.sha256(data.encode()).hexdigest()

def format_unix_date(unix_timestamp: int):
    dt_object = datetime.utcfromtimestamp(unix_timestamp)
    formatted_date = dt_object.strftime('%Y-%m-%d %H:%M:%S UTC')
    return formatted_date

def format_transactions(transactions: list):
    formatted_txs = []
    for tx in transactions:
        tx_type = tx['tx']['TransactionType']
        amount = int(tx['tx']['Amount']) / 1_000_000
        destination = tx['tx']['Destination']
        fee = int(tx['tx']['Fee'])
        date = format_unix_date(tx['tx']['date'])
        formatted_tx = f"Type: {tx_type} \n Amount: {amount} XRP \n Recipient: {destination} \n Fee: {fee} XRP drops \n Date: {date}"
        formatted_txs.append(formatted_tx)

    return "\n\n".join(formatted_txs)