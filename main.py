import random
import time

from aptos_sdk.account import Account
from aptos_sdk.client import RestClient, ClientConfig

from galaxy import sign_in_apt, get_txn_data
from logger import setup_gay_logger
from config import MIN_SLEEP, MAX_SLEEP

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

def claim(logger, account, verify_ids, signature, signature_expired_at):

    payload = {
        "function": "0xe7c7bb0e53fc6fb86aa7464645fbac96b96716463b4e2269c62945c135aa26fd::oat::claim",
        "type_arguments": [],
        "arguments": [
            "0x092d2f7ad00630e4dfffcca01bee12c84edf004720347fb1fd57016d2cc8d3f8",
            str(verify_ids),
            "0",
            "[CLAIM ONLY] Quest Three - Aptos Ecosystem Fundamentals",
            "1",
            str(signature_expired_at),
            str(signature)
        ],
        "type": "entry_function_payload"
    }

    return submit_and_log_transaction(account, payload, logger)

def main():
    keys_file = "keys_apt.txt"
    successful_keys_file = "claimed.txt"

    with open(keys_file, 'r') as file:
        keys = file.readlines()

    successful_keys = []

    for key in keys:
        key = key.strip()
        if not key:
            continue

        account = Account.load_key(key)
        address = account.address()
        logger = setup_gay_logger(str(address))

        token = sign_in_apt(logger, account)
        try:
            result = get_txn_data(logger, address, token)
        except Exception:
            continue
        if result is not None:
            verify_ids, signature, signature_expired_at = result
            if claim(logger, account, verify_ids, signature, signature_expired_at) == 0:
                successful_keys.append(key + '\n')
                with open(successful_keys_file, 'a') as sfile:
                    sfile.write(key + '\n')
                remaining_keys = [key for key in keys if key not in successful_keys]
                with open(keys_file, 'w') as file:
                    file.writelines(remaining_keys)
                sleep = random.randint(MIN_SLEEP, MAX_SLEEP)
                logger.info(f"Sleep for {sleep}s before next wallet")
                time.sleep(sleep)
            else:
                continue
        else:
            continue

if __name__ == "__main__":
    main()
