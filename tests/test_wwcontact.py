from pten.wwcontact import Contact

from .conftest import assert_ww_response


def test_contact(mocker):
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = {
        "errcode": 0,
        "errmsg": "ok",
        "access_token": "fake_token",
    }

    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {"errcode": 0, "errmsg": "ok"}

    contact = Contact("pten_keys_example.ini")

    userid = "userid"
    response = contact.get_user(userid)
    assert_ww_response(response)

    department_id = "2"
    response = contact.get_user_simple_list(department_id)
    assert_ww_response(response)

    department_id = "2"
    response = contact.get_user_list(department_id)
    assert_ww_response(response)

    size_type = "2"
    response = contact.get_join_qrcode(size_type)
    assert_ww_response(response)

    response = contact.get_user_id_list()
    assert_ww_response(response)

    response = contact.get_department_simplelist()
    assert_ww_response(response)

    response = contact.get_tag_list()
    assert_ww_response(response)
