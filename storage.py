import json
from utils import encode
from xrpl.wallet import Wallet
from typing import Dict, List
from xrpl.models.transactions import Transaction

class BaseAccount:
    def __init__(self, id: str, account_name: str, account_type: str, main_wallet: Wallet):
        self.id = id
        self.account_name = account_name
        self.account_type = account_type
        self.main_wallet = main_wallet

    def to_dict(self):
        return {
            'id': self.id,
            'account_name': self.account_name,
            'account_type': self.account_type,
            'main_wallet': wallet_to_dict(self.main_wallet)  # Updated line
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data['id'],
            account_name=data['account_name'],
            account_type=data['account_type'],
            main_wallet=wallet_from_dict(data['main_wallet'])  # Updated line
        )

    def __hash__(self):
        return hash((self.id, self.account_name))

    def __eq__(self, other):
        return self.id == other.id and self.account_name == other.account_name

class Account(BaseAccount):
    def __init__(self, account_name: str, account_type: str, pin: str, main_wallet: Wallet, phone_number: str, other_wallets: list[str] = []):
        super().__init__(phone_number, account_name, account_type, main_wallet)
        self.phone_number = phone_number
        self.other_wallets = other_wallets
        self.pin = pin
        # encode(pin)
    
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'phone_number': self.phone_number,
            'other_wallets': self.other_wallets,
            'pin': self.pin
        })
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            account_name=data['account_name'],
            account_type=data['account_type'],
            pin=data['pin'],
            main_wallet=wallet_from_dict(data['main_wallet']),
            phone_number=data['phone_number'],
            other_wallets=data['other_wallets']
        )

class MultiSigAccount(BaseAccount):
    def __init__(self, account_name: str, account_type: str, main_wallet: Wallet, signers: list[str], min_num_signers: int, open_txs: Dict[str, List[Transaction]] = {}):
        super().__init__(main_wallet.classic_address, account_name, account_type, main_wallet)
        self.signers = signers 
        self.min_num_signers = min_num_signers
        self.open_txs = open_txs

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'signers': self.signers,
            'min_num_signers': self.min_num_signers,
            'open_txs': {k: [tx.to_dict() for tx in v] for k, v in self.open_txs.items()}
        })
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            account_name=data['account_name'],
            account_type=data['account_type'],
            main_wallet=wallet_from_dict(data['main_wallet']),
            signers=data['signers'],
            min_num_signers=data['min_num_signers'],
            open_txs={k: [Transaction.from_dict(tx) for tx in v] for k, v in data['open_txs'].items()}  # Assuming Transaction has a from_dict method
        )

class Storage:
    def __init__(self, file_path='data.json'):
        self.file_path = file_path
        self.accounts = {}  # key: phone_number, value: Account
        self.multisig_accounts = {}  # key: id, value: MultiSigAccount
        self.load_data()

    def get_account(self, phone_number: str) -> Account:
        self.load_data()
        return self.accounts.get(phone_number)

    def get_multisig_account(self, wallet_addr: str) -> MultiSigAccount:
        self.load_data()
        return self.multisig_accounts.get(wallet_addr)

    def add_basic_account(self, basic_account: Account):
        self.accounts[basic_account.phone_number] = basic_account
        self.save_data()

    def add_multisig_account(self, multisig_account: MultiSigAccount):
        self.multisig_accounts[multisig_account.main_wallet.classic_address] = multisig_account
        self.save_data()
    
    def save_data(self):
        data = {
            'accounts': {k: v.to_dict() for k, v in self.accounts.items()},
            'multisig_accounts': {k: v.to_dict() for k, v in self.multisig_accounts.items()}
        }
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=4)

    def load_data(self):
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
            self.accounts = {k: Account.from_dict(v) for k, v in data.get('accounts', {}).items()}
            self.multisig_accounts = {k: MultiSigAccount.from_dict(v) for k, v in data.get('multisig_accounts', {}).items()}
        except FileNotFoundError as e:
            print(e)
            pass  # No data file exists yet

    def __str__(self):
        output = ["Storage:"]
        output.append("  Basic Accounts:")
        for phone_number, account in self.accounts.items():
            output.append(f"    {phone_number}: {account.__dict__}")
        output.append("  MultiSig Accounts:")
        for wallet_addr, account in self.multisig_accounts.items():
            output.append(f"    {wallet_addr}: {account.__dict__}")
        return '\n'.join(output)
    
def wallet_to_dict(wallet : Wallet):
    return {
        'classic_address': wallet.classic_address,
        'address' : wallet.address,
        'private_key' : wallet.private_key,
        'public_key' : wallet.public_key,
        'algorithm' : wallet.algorithm,
        'seed' : wallet.seed,
    }

def wallet_from_dict(data):
    return Wallet(
        master_address=data['classic_address'],
        private_key=data['private_key'],
        public_key=data['public_key'],
        algorithm=data['algorithm'],
        seed=data['seed']
    )
