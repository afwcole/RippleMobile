import os
from xrpl import wallet, transaction, utils
from xrpl.clients import JsonRpcClient
from xrpl.models.transactions import SignerEntry, SignerListSet, TrustSet, Payment
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.requests import AccountInfo
from schemas import TransactionRequest
from sms import send_sms
from storage import Account, MultiSigAccount, Storage
from utils import encode

db = Storage()

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/" #os.environ.get('JSON_RPC_URL')
CLIENT = JsonRpcClient(JSON_RPC_URL)

def register_multisig_account(account_name: str, min_num_signers: int, signer_phone_nums: list, msidn: str, pin: str):
    # VERIFY USER EXITS
    user_account = db.get_account(msidn)
    if not user_account:
        return "User not found."
    if user_account.pin != encode(pin):
        return "Incorrect PIN."
    
    # GET ALL SIGNER PHONE NUMBERS FROM STRING (MUST BE LESS THAN 8 SIGNERS)
    if len(signer_phone_nums) > 8:
        return "Too many signers, Multisign accounts can have a max of 8 signers"
    
    # GET EACH SIGNER'S ACCOUNT AND MAP INTO A LIST OF SIGNER ENTRIES
    signer_entries = []
    for signer_phone_num in signer_phone_nums:
        account_info = db.get_account(signer_phone_num)
        if (not account_info):
            return f"No account with this phone number: {signer_phone_num}"
    
        wallet_address = account_info.main_wallet.classic_address
        signer_entry = SignerEntry(account=wallet_address, signer_weight=1)
        signer_entries.append(signer_entry)
    try: 
        # CREATE THE MULTISIG WALLET
        multisig_wallet = wallet.generate_faucet_wallet(CLIENT)
        # CREATE WALLET'S FIRST SIGNER LIST SET TX
        signer_list_set_tx = SignerListSet(
            account=multisig_wallet.classic_address,
            signer_quorum=min_num_signers,
            signer_entries=signer_entries
        )
        transaction.submit_and_wait(signer_list_set_tx, CLIENT, multisig_wallet)

        # CREATE CORRESPONDING MULTISIG ACCOUNT FOR RIPPLE MOBILE STORAGE
        new_multisig_account = MultiSigAccount(
                account_name=account_name,
                account_type="MULTISIG",
                main_wallet=multisig_wallet,
                signers=signer_phone_nums,
                min_num_signers=min_num_signers
            )
        db.add_multisig_account(new_multisig_account)

        #UPDATE ALL SIGNER ACCOUNT'S INFO IN DB AND SEND OUT CORRESPONDING SMS
        for signer_phone_num in signer_phone_nums:
            signer_account = db.get_account(signer_phone_num)
            signer_account.other_wallets.append(new_multisig_account.id)
            db.add_account(signer_account)
            send_sms(
                f"Hey! \n{msidn} created a new Multisign account, and has made you 1 of {len(signer_phone_nums)} approvers for this account. A minimum of {min_num_signers} approvals are required for any transaction from this account. \
                \n Enjoy transacting with Ripple Mobile securely.", 
                signer_phone_num
            )
        return f"Succesfully created new Multisig account - {account_name}. SMS messages have been sent out to all signers."
    except Exception as e:
        send_sms(f"""Hey! \nSomething went wrong while creating your multi sign account, try again later""", msidn)
        print(e)

def request_multisig_tx(multisig_wallet_addr: str, transaction_request: TransactionRequest):
    # VERIFY USER EXITS
    user_account = db.get_account(transaction_request.sender_phone_num)
    if not user_account:
        return "User not found."
    if user_account.pin != transaction_request.pin:
        return "Incorrect PIN."
    
    # CREATE MULTISIG TRANSACTION
    recipient_account = db.get_account(transaction_request.recipient_phone_num)

    txn = Payment(
        account=multisig_wallet_addr,
        amount=utils.xrp_to_drops(transaction_request.amount_xrp),
        destination=recipient_account.main_wallet.classic_address
    )

    # GET MULTISIG ACCOUNT AND SAVE TXN TO ACCOUNT'S OPEN TXNS IN DB
    multisig_account = db.get_multisig_account(multisig_wallet_addr)
    if(not multisig_account):
        return "No Multisig account exists with that address"
    txn = transaction.autofill(txn, CLIENT, multisig_account.min_num_signers)
    multisig_account.open_txs[str(txn.sequence)] = [txn]
    db.add_multisig_account(multisig_account)

    try:
        # NOTIFY ALL SIGNERS OF NEW TXNS REQUIRING SIGNING
        for signer_phone in multisig_account.signers:
            send_sms(
                f"Hey {signer_phone}! \n{transaction_request.sender_phone_num} created a new Multisign transaction, transaction id - {txn.sequence}. This transaction requires approval from atleast {multisig_account.min_num_signers} approvers. Kindly go to approvals menu to approve this transaction.", 
                signer_phone
            )
    except Exception as e:
        print(e)
    return f"Successfully created transaction with id - {txn.sequence}"

def sign_multisig_tx(multisig_wallet_addr: str, tx_id: str, msidn: str, pin: str):
    # VERIFY USER EXITS
    user_account = db.get_account(msidn)
    if not user_account:
        return "User not found."
    if user_account.pin != encode(pin):
        return "Incorrect PIN."
    
    # GET MULTISG ACCOUNT AND BASE TX
    multisig_account = db.get_multisig_account(multisig_wallet_addr)
    if(not multisig_account):
        return "No Multisig account exists with that address"
    if msidn not in multisig_account.signers:
        return "You do not have permission to sign this transaction"

    signed_tx_list = multisig_account.open_txs.get(str(tx_id))

    # SIGN TXN AND UPDATE MULTISIG ACCOUNT'S OPEN TXS
    base_tx = signed_tx_list[0]
    signed_tx = transaction.sign(base_tx, user_account.main_wallet, multisign=True)
    signed_tx_list.append(signed_tx)
    multisig_account.open_txs[str(tx_id)] = signed_tx_list

    # SUBMIT AND REMOVE TXN FROM OPEN TXNS IF MIN NUM SIGNERS IS REACHED
    if (multisig_account.min_num_signers <= len(signed_tx_list) - 1):
        try:
            multi_tx = transaction.multisign(base_tx, signed_tx_list[1:])
            transaction.submit(multi_tx, CLIENT)
            multisig_account.open_txs.pop(str(tx_id)) # intended to remove multisign
            # NOTIFY SIGNERS THAT A SUCCESFUL TXN HAS OCCURED
            for signer_num in multisig_account.signers:
                send_sms(
                    f"""Hey! \n{signer_num}, SUCCESFUL transaction sent. {multisig_account.min_num_signers} out of {len(multisig_account.signers)} have signed the transaction from this Multisign account: {multisig_account.account_name}.\nEnjoy transacting with Ripple Mobile securely.""", 
                    signer_num
                )
        except Exception as e:
            print(e)
            return "something went wrong while trying to sign the transaction, try again later."
    db.add_multisig_account(multisig_account)
    return "successfully signed transaction"

def check_balance(wallet: str, phone_num:str, encoded_pin: str):
    user_account = db.get_account(phone_num)
    if not user_account:
        return "User not found."
    
    if user_account.pin != encoded_pin:
        return "Incorrect PIN."
    
    try:
        acct_info = AccountInfo(account=wallet, ledger_index="validated")
        response = CLIENT.request(acct_info)
        send_sms(f"Current balance is {int(response.result['account_data']['Balance']) / 1_000_000} XRP", phone_num)
        return f"{int(response.result['account_data']['Balance']) / 1_000_000} XRP"
    except Exception as e:
        print(e)
        return "Something went wrong, try again later"