# Ripple Mobile

This project aims to extend the capabilities of the Ripple blockchain by introducing a user-friendly and accessible payment layer using Unstructured Supplementary Service Data (USSD) technology. This integration facilitates seamless and secure financial transactions by enabling users to interact with the Ripple blockchain through basic mobile phones, bridging the gap between advanced blockchain technology and individuals without smartphones or reliable internet connections.

### Key Features:

- **USSD-Based Transactions**: This repository contains the codebase and documentation required to integrate USSD payment functionality directly with the Ripple blockchain. Users can initiate transactions, check balances, and perform various financial activities using a simplified USSD interface.
- **Accessibility**: By utilizing USSD technology, the project ensures that even users with basic mobile phones can access and engage with the Ripple blockchain, opening up financial opportunities to a broader segment of the population.
- **Secure Transactions**: The integration incorporates security measures to safeguard user data and transaction information, ensuring a secure environment for financial interactions.
- **Simple Interface**: The USSD interface is designed to be intuitive and user-friendly, guiding users through the transaction process step by step, even if they are not familiar with blockchain technology.
- **Real-time Updates**: Users receive immediate sms notifications about transaction statuses and account balances, enhancing transparency and user confidence in the payment process.

**Document contents**

- [Installation](#installation)
- [Contributing](#contributing)

# Installation

- [Virtualenv](#setup-with-virtualenv)

## Setup with Virtualenv

You can run the site locally or on your server simply by use of Virtualenv, which is the **recommended installation approach**.

#### Dependencies

- Python 3.6, 3.7, 3.8 or 3.9
- [Virtualenv[Optional]](https://virtualenv.pypa.io/en/stable/installation/)
- [VirtualenvWrapper[Optional]](https://virtualenvwrapper.readthedocs.io/en/latest/install.html) (optional)

### Installation

#### Creating your Virtualenv[Optional]

With [PIP](https://github.com/pypa/pip) and [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/)
installed, run:

    $ mkvirtualenv venv
    $ python --version

or 

With [PIP](https://github.com/pypa/pip) and [python3](https://docs.python.org/3/library/venv.html) **recommended approach**
installed, run:

    $ python3 -m venv /path/to/new/virtual/environment

Confirm that this is showing a compatible version of Python 3.x. If not, and you have multiple versions of Python installed on your system, you may need to specify the appropriate version when creating the virtualenv:

    $ deactivate
    $ rmvirtualenv 
    $ mkvirtualenv venv --python=python3.9
    $ python --version

Now we're ready to set up the project:

    $ git clone https://github.com/afwcole/RippleMobile.git
    $ cd /<app_home_directory>
    $ source /path/to/venv/bin/activate
    $ pip install -r requirements.txt

Next, we'll set up our local environment variables. We use [python-dotenv](https://github.com/theskumar/python-dotenv.git) to help with this. It reads environment variables located in a file name `.env` in the top level directory of the project.

    $ mv env.example .env [update enviromental variables and change accordingly]
    
allowed environment variables format `KEYWORDS`=`VALUES`: 

| KEYWORDS | VALUES | DEFAULT VALUE | VALUE TYPE | IS REQUIRED | 
| :------------ | :---------------------: | :------------------: | :------------------: | :------------------: |
| JSON_RPC_URL | - | https://s.altnet.rippletest.net:51234/ | string | true |
| SMS_URL | - | - | string | true | 
| SMS_AUTH_KEY | - | - | string | true |
| SMS_SENDER_ID | - | - | string | true |

Start app server with start script:

    $ uvicorn main:app --reload

# Contributing

This project was developed by [Elvis Segbawu](mailto:elvissegbawu@gmail.com) and [Adrian Cole](mailto:Afwcole@gmail.com)

Make a pull request to https://github.com/afwcole/RippleMobile.git
