from pten.wwapi import CorpApi, CORP_API_TYPE, BotApi, BOT_API_TYPE
from unittest.mock import MagicMock


def create_mock_response(else_response):
    def side_effect(url, *args, **kwargs):
        if "gettoken" in url:
            return MagicMock(
                json=lambda: {
                    "access_token": "fake_token",
                    "errcode": 0,
                    "errmsg": "ok",
                }
            )
        else:
            return MagicMock(json=lambda: else_response)

    return side_effect


def test_get_department_list(mocker):
    mock_get = mocker.patch("requests.get")
    mock_get.side_effect = create_mock_response(
        {
            "department": ["dep1", "dep2"],
            "errcode": 0,
            "errmsg": "ok",
        }
    )

    api = CorpApi("pten_keys_example.ini")
    response = api.http_call(CORP_API_TYPE["DEPARTMENT_LIST"])

    assert response["errcode"] == 0
    assert response["errmsg"] == "ok"
    assert response["department"] is not None


def test_bot_api(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {"errcode": 0, "errmsg": "ok"}

    api = BotApi("pten_keys_example.ini")
    response = api.http_call(
        BOT_API_TYPE["WEBHOOK_SEND"],
        {"msgtype": "text", "text": {"content": "hello from bot"}},
    )
    assert response["errcode"] == 0
    assert response["errmsg"] == "ok"


def test_jsapi_ticket(mocker):
    mock_get = mocker.patch("requests.get")
    mock_get.side_effect = create_mock_response(
        {
            "errcode": 0,
            "errmsg": "ok",
            "ticket": "fake_ticket",
        }
    )

    api = CorpApi("pten_keys_example.ini")
    corp_jsapi_ticket = api.get_corp_jsapi_ticket()
    assert corp_jsapi_ticket == "fake_ticket"

    app_jsapi_ticket = api.get_app_jsapi_ticket()
    assert app_jsapi_ticket == "fake_ticket"
