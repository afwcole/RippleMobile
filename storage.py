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

    def __hash__(self):
        return hash((self.id, self.account_name))

    def __eq__(self, other):
        return self.id == other.id and self.account_name == other.account_name

class Account(BaseAccount):
    def __init__(self, account_name: str, account_type: str, pin: str, main_wallet: Wallet, phone_number: str, other_wallets: list[str]):
        super().__init__(phone_number, account_name, account_type, main_wallet)
        self.phone_number = phone_number
        self.other_wallets = other_wallets
        self.pin = encode(pin)

class MultiSigAccount(BaseAccount):
    def __init__(self, account_name: str, account_type: str, main_wallet: Wallet, signers: list[str], min_num_signers: int):
        super().__init__(main_wallet.classic_address, account_name, account_type, main_wallet)
        self.signers = signers 
        self.min_num_signers = min_num_signers
        self.open_txs: Dict[str, List[Transaction]] = {}

class Storage:
    def __init__(self):
        self.accounts = {}  # key: phone_number, value: Account
        self.multisig_accounts = {}  # key: id, value: MultiSigAccount

    def get_basic_account(self, phone_number: str) -> Account:
        return self.accounts.get(phone_number)

    def get_multisig_account(self, wallet_addr: str) -> MultiSigAccount:
        return self.multisig_accounts.get(wallet_addr)

    def add_basic_account(self, basic_account: Account):
        self.accounts[basic_account.phone_number] = basic_account

    def add_multisig_account(self, multisig_account: MultiSigAccount):
        self.multisig_accounts[multisig_account.main_wallet.classic_address] = multisig_account

    def __str__(self):
        output = ["Storage:"]
        output.append("  Basic Accounts:")
        for phone_number, account in self.accounts.items():
            output.append(f"    {phone_number}: {account.__dict__}")
        output.append("  MultiSig Accounts:")
        for wallet_addr, account in self.multisig_accounts.items():
            output.append(f"    {wallet_addr}: {account.__dict__}")
        return '\n'.join(output)
    