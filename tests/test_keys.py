from .conftest import use_real_keys
from pten.keys import Keys
import os
import pten
import pytest


pytestmark = pytest.mark.skipif(use_real_keys, reason="Skipping when using real keys")


def test_key_path_not_exist():
    keys = Keys("not_exist.ini")
    with pytest.raises(FileNotFoundError):
        keys.get_bot_weebhook_key()


@pytest.mark.parametrize(
    "section,option,expected",
    [
        ("ww", "app_aes_key", "9z1Cj9cSd7WtEV3hOWo5iMQlFkSP9Td1ejzsV9WhCmO"),
        ("ww", "app_agentid", "1000005"),
        ("ww", "app_secret", "jVJF_EBWCVA_KVi_89YnY1T1bPD8-0PdqQ2rXc_Pgmj5"),
        ("ww", "app_token", "zJdPmXg8E4J1mMdnzP8d"),
        ("ww", "contact_sync_secret", "G4PC19fIwfsykabdv_drNVlOIe_crBvay3sUX8DhGss"),
        ("ww", "corpid", "wwdb63ff5ae01cd4b4"),
        ("ww", "webhook_key", "7ande764-52a4-43d7-a252-05e8abcdb863"),
        ("fs", "receive_id", "ou_84a7b7e2d5219af3c6b0e4d8a2f1c5d6"),
        ("notice", "deepseek_api_key", "sk-0a6e5b4e8b4c0e1a5b6b8e0e4d5aefb"),
        ("notice", "seniverse_api_key", "v5bFw3o1pSmbGvuEN"),
    ],
)
def test_get_key(key_filepath_example, section, option, expected):
    keys = Keys(key_filepath_example)
    assert keys.get_key(section, option) == expected


@pytest.mark.parametrize(
    "section,options,expected",
    [
        (
            "proxies",
            ["http", "https"],
            {
                "http": "http://xxx:xxx@xxx.xxx.xxx.xxx:8888",
                "https": "http://xxx:xxx@xxx.xxx.xxx.xxx:8888",
            },
        )
    ],
)
def test_get_keys(key_filepath_example, section, options, expected):
    keys = Keys(key_filepath_example)
    assert keys.get_keys(section, options) == expected


def test_get_debug_mode(key_filepath_example):
    keys = Keys(key_filepath_example)
    assert keys.get_debug_mode() is False

    keys_no_debug_mode = Keys("pten_keys_example_min.ini")
    assert keys_no_debug_mode.get_debug_mode() is False


def test_proxies(key_filepath_example):
    keys = Keys(key_filepath_example)
    proxies_expected = {
        "http": "http://xxx:xxx@xxx.xxx.xxx.xxx:8888",
        "https": "http://xxx:xxx@xxx.xxx.xxx.xxx:8888",
    }
    assert keys.get_proxies() == proxies_expected

    keys_no_proxies = Keys("pten_keys_example_min.ini")
    assert keys_no_proxies.get_proxies() is None


def test_bot_weebhook_key(key_filepath_example):
    keys = Keys(key_filepath_example)
    assert keys.get_bot_weebhook_key() == "7ande764-52a4-43d7-a252-05e8abcdb863"


def test_get_log_path_default(key_filepath_example):
    # pten_keys_example.ini 中 log_path 被注释掉，回退默认值
    keys = Keys(key_filepath_example)
    assert keys.get_log_path() == pten.DEFAULT_LOG_PATH


def test_get_log_path_configured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ini = tmp_path / "keys_with_log_path.ini"
    ini.write_text("[globals]\ndebug_mode=False\nlog_path=my.log\n", encoding="utf-8")
    keys = Keys(str(ini))
    # 配置值应被原样读出
    assert keys.get_log_path() == "my.log"
    # 构造 Keys 时应顺带把日志 handler 切到该路径
    expected = os.path.normpath(os.path.join(str(tmp_path), "my.log"))
    assert os.path.normpath(pten._current_log_path) == expected


def test_access_token_cache_per_key(key_filepath_example, tmp_path):
    keys = Keys(key_filepath_example)
    # token 缓存文件重定向到临时目录
    keys.TOKEN_PATH = tmp_path / "pten_token.json"

    keys.save_access_token("ww_xxx", "ww-token")
    keys.save_access_token("fs_yyy", "fs-token")

    # 多个 token_key（企业微信 ww_* / 飞书 fs_*）在同一实例上互不串扰
    assert keys.get_access_token("ww_xxx") == "ww-token"
    assert keys.get_access_token("fs_yyy") == "fs-token"


def test_optional_config_missing(tmp_path):
    # 可选配置（contact_sync_secret / fs 默认接收者）未写入时返回 None 而不是
    # 抛异常——contact_sync_secret 曾因捕获了错误的异常类型导致兜底从未生效
    ini = tmp_path / "keys_min.ini"
    ini.write_text("[ww]\ncorpid=x\n[fs]\napp_id=cli_x\n", encoding="utf-8")
    keys = Keys(str(ini))
    assert keys.get_contact_sync_secret() is None
    assert keys.get_fs_receive_id() is None
    assert keys.get_fs_receive_id_type() is None


def test_keys_file_utf8_comment(tmp_path):
    # UTF-8 保存的中文注释应能正常读取（本地编码非 UTF-8 时曾触发解码错误）
    ini = tmp_path / "keys_utf8.ini"
    ini.write_text("[fs]\n;中文注释\nreceive_id=ou_x\n", encoding="utf-8")
    keys = Keys(str(ini))
    assert keys.get_key("fs", "receive_id") == "ou_x"


def test_keys_file_utf8_bom(tmp_path):
    # Windows 记事本保存的 UTF-8 with BOM 同样应能正常读取
    # （用 utf-8 读会抛 MissingSectionHeaderError，不被 UnicodeDecodeError 回退捕获）
    ini = tmp_path / "keys_bom.ini"
    ini.write_text("[fs]\n;中文注释\nreceive_id=ou_x\n", encoding="utf-8-sig")
    keys = Keys(str(ini))
    assert keys.get_key("fs", "receive_id") == "ou_x"


def test_list_llm_providers(tmp_path):
    ini = tmp_path / "keys.ini"
    ini.write_text(
        "[notice]\nseniverse_api_key=k\n"
        "[llm:openai]\nbase_url=x\napi_key=y\nmodel=z\n"
        "[llm:qwen]\nbase_url=x\napi_key=y\nmodel=z\n",
        encoding="utf-8",
    )
    keys = Keys(str(ini))
    # 按文件中出现顺序返回所有 [llm:<name>] 段的 name
    assert keys.list_llm_providers() == ["openai", "qwen"]
