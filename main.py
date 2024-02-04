from aptos_sdk.account import Account
from aptos_sdk.client import RestClient, ClientConfig

ClientConfig.max_gas_amount = 100_00
# This adjustment decreases the required balance for transaction execution.
# It changes the upper limit for gas, avoiding trigger safety shut down.

Rest_Client = RestClient("https://fullnode.mainnet.aptoslabs.com/v1")

def submit_and_log_transaction(account, payload, logger):
    try:
        txn = Rest_Client.submit_transaction(account, payload)
        Rest_Client.wait_for_transaction(txn)
        logger.info(f'Success: https://explorer.aptoslabs.com/txn/{txn}?network=mainnet')
        return 0
    except AssertionError as e:
        logger.error(f"AssertionError caught: {e}")
        return 1
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}")
        return 1