import os
from xrpl import wallet, transaction, utils
from xrpl.clients import JsonRpcClient
from xrpl.models.transactions import SignerEntry, SignerListSet, TrustSet, Payment
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.requests import AccountInfo
from schemas import TransactionRequest, SIMMessage
from sms import send_sms
from storage import Account, MultiSigAccount, Storage
from utils import encode

db = Storage()

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/" #os.environ.get('JSON_RPC_URL')
CLIENT = JsonRpcClient(JSON_RPC_URL)

def register_multisig_account(account_name: str, min_num_signers: int, signer_phone_nums: list, msidn: str, pin: str, sim:bool=False):
    # VERIFY USER EXITS
    user_account = db.get_account(msidn)
    response, sms = "", None
    if not user_account:
        return "User not found.", sms
    if user_account.pin != encode(pin):
        return "Incorrect PIN.", sms
    
    # GET ALL SIGNER PHONE NUMBERS FROM STRING (MUST BE LESS THAN 8 SIGNERS)
    if len(signer_phone_nums) > 8:
        return "Too many signers, Multisign accounts can have a max of 8 signers", sms
    
    # GET EACH SIGNER'S ACCOUNT AND MAP INTO A LIST OF SIGNER ENTRIES
    signer_entries = []
    for signer_phone_num in signer_phone_nums:
        account_info = db.get_account(signer_phone_num)
        if (not account_info):
            return f"No account with this phone number: {signer_phone_num}", sms
    
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
        sms = []
        for signer_phone_num in signer_phone_nums:
            signer_account = db.get_account(signer_phone_num)
            signer_account.other_wallets.append(new_multisig_account.id)
            db.add_account(signer_account)
            if msidn != signer_account.phone_number:
                message = f"Hey! \n{msidn} created a new Multisign account, and has made you 1 of {len(signer_phone_nums)} approvers for this account. A minimum of {min_num_signers} approvals are required for any transaction from this account. \
                        \n Enjoy transacting with Ripple Mobile securely."
            else:
                message = f"Hey! your request to create a multisign was successful."
            if not sim:
                send_sms(message, signer_phone_num)
            else:
                sms.append(
                    SIMMessage(
                        TO=signer_phone_num,
                        MESSAGE=message
                    )
                )

        response = f"We are creating your shared(multi-sig) account - {account_name}. you and other signers will be notified via SMS when complete."
    except Exception as e:
        response = f"""Hey! \nSomething went wrong while creating your multi sign account, try again later"""
        send_sms(response, msidn)
        print(e)

    return response, sms

def request_multisig_tx(multisig_wallet_addr: str, transaction_request: TransactionRequest, sim=False):
    # VERIFY USER EXITS
    user_account, sms = db.get_account(transaction_request.sender_phone_num), None
    
    if not user_account:
        return "User not found.", sms
    
    if user_account.pin != transaction_request.pin:
        return "Incorrect PIN.", sms
    
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
        return "No Multisig account exists with that address", sms
    txn = transaction.autofill(txn, CLIENT, multisig_account.min_num_signers)
    multisig_account.open_txs[str(txn.sequence)] = [txn]
    db.add_multisig_account(multisig_account)

    try:
        sms = []
        # NOTIFY ALL SIGNERS OF NEW TXNS REQUIRING SIGNING
        for signer_phone in multisig_account.signers:
            message = f"Hey {signer_phone}! \n{transaction_request.sender_phone_num} created a new Multisign transaction, transaction id - {txn.sequence}. This transaction requires approval from at least {multisig_account.min_num_signers} approvers. Kindly go to approvals menu in MultiSign Acc/Shared accounts to approve this transaction."
            if not sim:
                send_sms(message, signer_phone)
            else:
                sms.append(
                    SIMMessage(
                        TO=signer_phone,
                        MESSAGE=message
                    )
                )
        response = f"Successfully created transaction with id - {txn.sequence}"
         
    except Exception as e:
        response = "Something went wrong, try again later"
        print(e)

    return response, sms

def sign_multisig_tx(multisig_wallet_addr: str, tx_id: str, msidn: str, pin: str, sim=False):
    # VERIFY USER EXITS
    user_account, sms, response = db.get_account(msidn), None, "Could not process request at this time"

    if not user_account:
        return "User not found.", sms
    if user_account.pin != encode(pin):
        return "Incorrect PIN.", sms
    
    # GET MULTISG ACCOUNT AND BASE TX
    multisig_account = db.get_multisig_account(multisig_wallet_addr)
    if(not multisig_account):
        return "No Multisig account exists with that address", sms
    if msidn not in multisig_account.signers:
        return "You do not have permission to sign this transaction", sms

    signed_tx_list = multisig_account.open_txs.get(str(tx_id))

    # SIGN TXN AND UPDATE MULTISIG ACCOUNT'S OPEN TXS
    base_tx = signed_tx_list[0]
    signed_tx = transaction.sign(base_tx, user_account.main_wallet, multisign=True)
    signed_tx_list.append(signed_tx)
    multisig_account.open_txs[str(tx_id)] = signed_tx_list
    base_tx_dict = base_tx.to_dict()

    print()

    # rswHop32YrfnRudHvSckRwT6wZVvJheZRG
    
    response = "successfully signed transaction"
    # SUBMIT AND REMOVE TXN FROM OPEN TXNS IF MIN NUM SIGNERS IS REACHED
    if multisig_account.min_num_signers<=(len(signed_tx_list) - 1):
        amount, recipient = int(base_tx_dict['amount'])/1_000_000, db.get_account_by_address(base_tx_dict['destination'])
        try:
            sms = []
            multi_tx = transaction.multisign(base_tx, signed_tx_list[1:])
            transaction.submit(multi_tx, CLIENT)
            multisig_account.open_txs.pop(str(tx_id))
            # NOTIFY SIGNERS THAT A SUCCESFUL TXN HAS OCCURED
            for signer_num in multisig_account.signers:
                message = f"""Hey! \n{signer_num}, SUCCESFUL transaction sent. {multisig_account.min_num_signers} out of {len(multisig_account.signers)} have signed the transaction from this Multisign account: {multisig_account.account_name}.\nEnjoy transacting with Ripple Mobile securely."""
                if not sim:
                    send_sms(message, signer_num)
                else:
                    sms.append(SIMMessage(TO=signer_num, MESSAGE=message))
                
            if recipient:
                message = f"You have received {amount} XRP from MultiSign Account - {multisig_account.account_name}."
                if not sim:send_sms(message, recipient)
                else:sms.append(SIMMessage(TO=recipient.phone_number, MESSAGE=message))
        except Exception as e:
            print(e)
            response = "something went wrong while trying to sign the transaction, try again later."
    
    db.add_multisig_account(multisig_account)
    return response, sms

def check_balance(wallet: str, phone_num:str, encoded_pin: str, sim=False):
    user_account, sms = db.get_account(phone_num), None
    if not user_account:
        return "User not found.", sms
    
    if user_account.pin != encoded_pin:
        return "Incorrect PIN.", sms
    
    try:
        acct_info = AccountInfo(account=wallet, ledger_index="validated")
        account = db.get_multisig_account(acct_info.account)
        if not account:
            raise ValueError
        account_name = account.account_name
        response = CLIENT.request(acct_info)
        message = f"Current balance for multisign account - {account_name} is {int(response.result['account_data']['Balance']) / 1_000_000} XRP"
        if not sim:
            send_sms(message, phone_num)
        else:
            sms = [SIMMessage(
                TO=phone_num,
                MESSAGE=message
            )]
        response = f"{int(response.result['account_data']['Balance']) / 1_000_000} XRP"
    except Exception as e:
        print(e)
        response = "Something went wrong, try again later"
    
    return response, sms