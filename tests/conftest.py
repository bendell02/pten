import os
import pytest
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, "..", "src"))

use_real_keys = False  # True False. Set to True when you want to use real keys
enable_long_time_tests = False  # True False. Set to True to run long time tests


@pytest.fixture()
def key_filepath_example():
    if use_real_keys:
        return "pten_keys.ini"
    else:
        return "pten_keys_example.ini"


def assert_response(response):
    assert response["errcode"] == 0
    assert response["errmsg"] == "ok"


def assert_fs_response(response):
    assert response["code"] == 0
    assert response["msg"] == "success"
