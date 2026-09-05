import os
import pytest
import sys
from unittest.mock import MagicMock

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, "..", "src"))

from pten.keys import Keys  # 需要先保证 src 在 sys.path 上

use_real_keys = False  # True False. Set to True when you want to use real keys
enable_long_time_tests = False  # True False. Set to True to run long time tests


@pytest.fixture()
def key_filepath_example():
    if use_real_keys:
        return "pten_keys.ini"
    else:
        return "pten_keys_example.ini"


@pytest.fixture()
def fs_keys(tmp_path):
    keys = Keys("pten_keys_example.ini")
    # token 缓存文件重定向到临时目录，避免测试污染仓库根目录的 pten_token.json
    keys.TOKEN_PATH = tmp_path / "pten_token.json"
    return keys


@pytest.fixture()
def fs_keys_no_receiver(tmp_path):
    # 未配置默认接收者的 [fs] 配置，用于默认接收者缺失的场景
    ini = tmp_path / "keys_no_receiver.ini"
    ini.write_text("[fs]\napp_id=cli_x\napp_secret=s\n", encoding="utf-8")
    keys = Keys(str(ini))
    keys.TOKEN_PATH = tmp_path / "pten_token.json"
    return keys


def assert_ww_response(response):
    assert response["errcode"] == 0
    assert response["errmsg"] == "ok"


def assert_fs_response(response):
    assert response["code"] == 0
    assert response["msg"] == "success"


def create_fs_mock_response(else_response):
    """按 URL 分发 mock：token 端点返回假 token，其余端点返回 else_response"""

    def side_effect(url, *args, **kwargs):
        if "tenant_access_token" in url:
            return MagicMock(
                json=lambda: {
                    "code": 0,
                    "msg": "ok",
                    "tenant_access_token": "t-fake",
                    "expire": 7200,
                }
            )
        return MagicMock(json=lambda: else_response)

    return side_effect
