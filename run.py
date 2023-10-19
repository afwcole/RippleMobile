from multisig import (
    register_multisig_account,
    request_multisig_tx,
    db,
    sign_multisig_tx,
)
from storage import Account, Storage
from xrpl import wallet
from xrpl.clients import JsonRpcClient

CLIENT = JsonRpcClient("https://s.altnet.rippletest.net:51234/")

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

addr = register_multisig_account(
    account_name=account_name,
    min_num_signers=min_num_signers,
    signers_phones_str=signers_phone_str,
    msidn=phone_num,
    pin=pin,
)
# tx_id = request_multisig_tx(addr, "233456498733", pin)
# sign_multisig_tx(addr, tx_id, "233123456789", "1234")
# sign_multisig_tx(addr, tx_id, "233456444333", "1234")
# sign_multisig_tx(addr, tx_id, "233678918273", "1234")
