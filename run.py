from xrpl import wallet
from multisig import (
    register_multisig_account,
    request_multisig_tx,
    sign_multisig_tx,
)
from schemas import TransactionRequest
from xrpl.clients import JsonRpcClient

from storage import Account, Storage

CLIENT = JsonRpcClient("https://s.altnet.rippletest.net:51234/")

db = Storage()

db.add_basic_account(
    basic_account=Account(
        "base",
        "BASIC",
        "1234",
        wallet.generate_faucet_wallet(CLIENT),
        "233456498733",
        [],
    )
)

db.add_basic_account(
    basic_account=Account(
        "signer1",
        "BASIC",
        "1234",
        wallet.generate_faucet_wallet(CLIENT),
        "233456444333",
        [],
    )
)

db.add_basic_account(
    basic_account=Account(
        "signer2",
        "BASIC",
        "1234",
        wallet.generate_faucet_wallet(CLIENT),
        "233678918273",
        [],
    )
)

db.add_basic_account(
    basic_account=Account(
        "signer3",
        "BASIC",
        "1234",
        wallet.generate_faucet_wallet(CLIENT),
        "233123456789",
        [],
    )
)

account_name = "random account"
min_num_signers = 2
signers_phone_str = "233123456789, 233456444333, 233678918273"
phone_num = "233456498733"
pin = "1234"

register_multisig_account(
    account_name=account_name,
    min_num_signers=min_num_signers,
    signers_phones_str=signers_phone_str,
    msidn=phone_num,
    pin=pin,
)

request_multisig_tx(
    "r9YD66XvVQkQrNq1HZXvc2iwGKuBMWf8XQ", 
    TransactionRequest(
        sender_phone_num="233456498733",
        recipient_phone_num="233123456789",
        amount_xrp=20,
        pin="1234"
    )
)

sign_multisig_tx("r9YD66XvVQkQrNq1HZXvc2iwGKuBMWf8XQ", "42186193", "233123456789", "1234")
sign_multisig_tx("r9YD66XvVQkQrNq1HZXvc2iwGKuBMWf8XQ", "42186193", "233456444333", "1234")