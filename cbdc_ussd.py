import requests
import phonenumbers

API_BASE_URL = "http://localhost:8000"

def get_valid_phone_number(prompt: str) -> str:
    phone_num = input("Enter phone number: ")

    if not is_valid_phone_number(phone_num): 
        print("Invalid phone number!")
        exit()

    return phone_num

def is_valid_phone_number(phone_num: str) -> bool:
    try:
        parsed_number = phonenumbers.parse(phone_num, 'GH')
        if not phonenumbers.is_valid_number(parsed_number):
            return False
        return True
    except phonenumbers.NumberParseException:
        return False

def get_valid_pin() -> str:
    pin = input("Enter PIN: ")

    if not is_valid_pin(pin): 
        print("Invalid PIN. Ensure it's 4 digits long.")
        exit()

    return pin

def is_valid_pin(pin: str) -> bool:
    return len(pin) == 4 and pin.isdigit()


def main_menu():
    print("\n-----------------------------------------------")
    print("Welcome to USSD simulation CLI!")
    print("1. Register New Wallet")
    print("2. Check Wallet Balance")
    print("3. Send XRP")
    print("4. Exit")
    
    choice = input("Choose an option (1/2/3/4): ")
    print("\n")
    if choice == "1":
        register_account()
    elif choice == "2":
        check_balance()
    elif choice == "3":
        send_xrp()
    elif choice == "4":
        exit()
    else:
        print("Invalid option.")
        main_menu()

def register_account():
    phone_num = get_valid_phone_number("Enter phone number: ")
    name = input("Enter name: ")
    pin = get_valid_pin()
    print("\n")
    
    payload = {
        "phone_num": phone_num,
        "name": name,
        "pin": pin
    }
    
    print("Registering account...")
    response = requests.post(f"{API_BASE_URL}/account/register", json=payload)
    if response.status_code == 200:
        print("Account registered successfully!")
    else:
        print(f"Error: {response.text}")

    main_menu()

def check_balance():
    phone_num = get_valid_phone_number("Enter phone number: ")
    pin = get_valid_pin()
    print("\n")
    
    response = requests.get(f"{API_BASE_URL}/account/balance/{phone_num}/{pin}")
    if response.status_code == 200:
        balance = response.json().get('balance')
        print(f"Your balance is: {balance} XRP")
    else:
        print(f"Error: {response.text}")
    
    main_menu()

def send_xrp():
    sending_phone_num = get_valid_phone_number("Enter phone number: ")
    destination_phone_num = get_valid_phone_number("Enter recipient's phone number: ")
    amount_xrp = float(input("Enter amount to send in XRP: "))
    pin = get_valid_pin()
    print("\n")

    payload = {
        "sender_phone_num": sending_phone_num,
        "recipient_phone_num": destination_phone_num,
        "amount_xrp": amount_xrp,
        "pin": pin
    }

    response = requests.post(f"{API_BASE_URL}/transact/", json=payload)
    if response.status_code == 200:
        print("XRP sent successfully!")
    else:
        print(f"Error: {response.text}")

    main_menu()

if __name__ == "__main__":
    main_menu()