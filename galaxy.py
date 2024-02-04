import json
from datetime import timedelta, datetime
from time import time
from pyuseragents import random as random_user_agent
import requests
from config import SMART_PROXY_URL, CAPCHA_API_KEY
import uuid
from twocaptcha import TwoCaptcha

galaxy_query = 'https://graphigo.prd.galaxy.eco/query'

proxies = {
    'http': SMART_PROXY_URL,
    'https': SMART_PROXY_URL
}

solver = TwoCaptcha(CAPCHA_API_KEY)

def galaxy_headers(token):
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-GB,en;q=0.9",
        "Authorization": token,
        "Content-Type": "application/json",
        "Origin": "https://galxe.com",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": str(random_user_agent())
    }
    return headers

def sign_in_apt(logger, account):
    apt_address = account.address()
    public_key = account.public_key()

    try:
        now = datetime.utcnow()
        next_day = now + timedelta(days=7)
        iso_time_next_day = next_day.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        current_time = int(time())
        rounded_time = int(current_time - (current_time % 3600))

        message = (f"Galxe.com wants you to sign in with your Aptos account: "
                   f"{apt_address}; "
                   f"<Public key: {public_key}>, "
                   f"<Version: 1>, "
                   f"<Chain ID: 1>, "
                   f"<Nonce: {rounded_time}>, "
                   f"<Expiration Time: {iso_time_next_day}>")

        full_message = f'APTOS\nmessage: {message}\nnonce: {rounded_time}'

        signature = account.sign(full_message.encode('utf-8'))

        data = {
            "operationName": "SignIn",
            "variables": {
                "input": {
                    "address": str(apt_address),
                    "message": message,
                    "signature": str(signature.signature.hex())
                }
            },
            "query": "mutation SignIn($input: Auth) {\n  signin(input: $input)\n}\n"
        }

        response = requests.post(galaxy_query, json=data, proxies=proxies)

        if response.status_code == 200 and 'signin' in response.text:
            signin = response.json()['data']['signin']
            logger.info('Got the signIn token')
            return signin
        else:
            logger.error(f"{apt_address} Login failed."
                         f"\nResponse code: {response.status_code}."
                         f"\nResponse content {response.content}")
            return None

    except Exception as e:
        logger.critical(f"{apt_address} Login failed."
                        f"\nException: {e}")
        return None


def get_captcha_output(logger):
    try:
        logger.info("Starting solve captcha")
        now_ms = int(datetime.now().timestamp() * 1000)
        result = solver.geetest_v4(captcha_id='244bcb8b9846215df5af4c624a750db4',
                                   url=f'https://gcaptcha4.geetest.com/load?captcha_id=244bcb8b9846215df5af4c624a750db4&'
                                       f'challenge={str(uuid.uuid4())}&client_type=web&lang=en-us&callback=geetest_{now_ms}',
                                   callback=f'geetest_{now_ms}')
        code_str = result.get('code')
        if code_str:
            code_dict = json.loads(code_str)
            lot_number = code_dict.get('lot_number')
            pass_token = code_dict.get('pass_token')
            gen_time = code_dict.get('gen_time')
            captcha_output = code_dict.get('captcha_output')
            logger.info("Got captcha data")
            return lot_number, pass_token, gen_time, captcha_output
        else:
            logger.error("No 'code' field in captcha result")
    except Exception as e:
        logger.critical(f"Error while solving captcha."
                        f"\nException: {e}")


def get_txn_data(logger, address, token):
    lot_number, pass_token, gen_time, captcha_output = get_captcha_output(logger)
    try:

        payload = {
            "operationName": "PrepareParticipate",
            "variables": {
                "input": {
                    "signature": "",
                    "campaignID": "GCQC1twFSe",
                    "address": f"APTOS:{address}",
                    "mintCount": 1,
                    "chain": "APTOS",
                    "captcha": {
                        "lotNumber": str(lot_number),
                        "captchaOutput": str(captcha_output),
                        "passToken": str(pass_token),
                        "genTime": str(gen_time)
                    }
                }
            },
            "query": """mutation PrepareParticipate($input: PrepareParticipateInput!) {
              prepareParticipate(input: $input) {
                allow
                disallowReason
                signature
                nonce
                mintFuncInfo {
                  funcName
                  nftCoreAddress
                  verifyIDs
                }
                aptosTxResp {
                  signatureExpiredAt
                  tokenName
                  __typename
                }
                __typename
              }
            }
            """
        }

        response = requests.post(galaxy_query, headers=galaxy_headers(token), json=payload, proxies=proxies)

        if response.status_code == 200:
            response_data = response.json()
            print(json.dumps(response_data, indent=4))
            if 'data' in response_data and 'prepareParticipate' in response_data['data']:
                if response_data['data']['prepareParticipate']['allow']:
                    verify_ids = response_data['data']['prepareParticipate']['mintFuncInfo'].get('verifyIDs')
                    signature = response_data['data']['prepareParticipate'].get('signature')
                    signature_expired_at = response_data['data']['prepareParticipate']['aptosTxResp'].get(
                        'signatureExpiredAt')
                    logger.info("Transaction data gathered successfully.")
                    return verify_ids, signature, signature_expired_at
                else:
                    disallow_reason = response_data['data']['prepareParticipate'].get('disallowReason', '')
                    if "Exceed limit, available claim count is 0" in disallow_reason:
                        logger.info(f"The OAT is already claimed or address is not eligible. "
                                    f"\n(in both cases responses are the same)")
                        return None
                    else:
                        logger.error(f"Transaction preparation failed due to: {disallow_reason}")
                        return None
            else:
                logger.error("Transaction preparation failed. Invalid response format.")
                return None
        else:
            logger.error(f"{address} Request failed."
                         f"\nResponse code: {response.status_code}."
                         f"\nResponse content: {response.text}")
            return None
    except Exception as e:
        logger.critical(f"Exception occurred."
                        f"\nException: {e}")
    return None