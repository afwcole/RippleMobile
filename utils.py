import json, hashlib
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
    return hashlib.sha256(text.encode()).hexdigest()