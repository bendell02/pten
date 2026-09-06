from pten.wwcrypt import WXBizMsgCrypt
from pten.keys import Keys
import pytest


@pytest.fixture()
def wwcpt(key_filepath_example):
    keys = Keys(key_filepath_example)
    CORP_ID = keys.get_key("ww", "corpid")
    API_TOKEN = keys.get_key("ww", "app_token")
    API_AES_KEY = keys.get_key("ww", "app_aes_key")

    wwcpt = WXBizMsgCrypt(API_TOKEN, API_AES_KEY, CORP_ID)
    return wwcpt


def test_EncryptMsg(wwcpt):
    sReplyMsg = "hello"
    nonce = "1741290221"
    ret, send_msg = wwcpt.EncryptMsg(sReplyMsg=sReplyMsg, sNonce=nonce)
    assert ret == 0
