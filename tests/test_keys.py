import os
from pathlib import Path

import pytest

import pten
from pten.keys import Keys


def test_key_path_not_exist():
    keys = Keys("not_exist.ini")
    with pytest.raises(FileNotFoundError):
        keys.get_bot_weebhook_key()


def _write_keys_ini(path, corpid="x"):
    """写一个最小 keys 文件，corpid 作为标记以区分文件来源"""
    path.write_text(f"[ww]\ncorpid={corpid}\n", encoding="utf-8")


def _patch_home(monkeypatch, home):
    """把 Path.home() 指到给定目录；Windows 上 USERPROFILE/HOME 都要设"""
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))


def _setup_lookup_dirs(tmp_path, monkeypatch, cwd_keys=True, home_keys=True):
    """搭好查找链测试目录：cwd 与 ~/.pten（按需放 pten_keys.ini），返回 home 目录"""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    if cwd_keys:
        _write_keys_ini(cwd / "pten_keys.ini", corpid="cwd")
    home = tmp_path / "home"
    home.mkdir()
    if home_keys:
        (home / ".pten").mkdir()
        _write_keys_ini(home / ".pten" / "pten_keys.ini", corpid="home")
    _patch_home(monkeypatch, home)
    monkeypatch.delenv("PTEN_KEYS_FILE", raising=False)
    return home


def test_keys_filepath_explicit_beats_env(tmp_path, monkeypatch):
    # 显式传入的路径优先级最高，即使环境变量也指向有效文件
    explicit = tmp_path / "explicit.ini"
    _write_keys_ini(explicit, corpid="explicit")
    env_file = tmp_path / "env_keys.ini"
    _write_keys_ini(env_file, corpid="env")
    monkeypatch.setenv("PTEN_KEYS_FILE", str(env_file))

    keys = Keys(str(explicit))
    assert keys.get_key("ww", "corpid") == "explicit"


def test_keys_filepath_explicit_missing_no_fallback(tmp_path, monkeypatch):
    # 显式传入但文件不存在：不回退到环境变量，取 key 时报 FileNotFoundError
    env_file = tmp_path / "env_keys.ini"
    _write_keys_ini(env_file, corpid="env")
    monkeypatch.setenv("PTEN_KEYS_FILE", str(env_file))

    keys = Keys("not_exist.ini")
    assert keys.keys_filepath == Path("not_exist.ini")
    with pytest.raises(FileNotFoundError):
        keys.get_key("ww", "corpid")


def test_keys_filepath_env_var_beats_cwd_and_home(tmp_path, monkeypatch):
    # 环境变量 PTEN_KEYS_FILE 优先于当前目录与 ~/.pten 的探测结果
    _setup_lookup_dirs(tmp_path, monkeypatch)
    env_file = tmp_path / "env_keys.ini"
    _write_keys_ini(env_file, corpid="env")
    monkeypatch.setenv("PTEN_KEYS_FILE", str(env_file))

    keys = Keys()
    assert keys.get_key("ww", "corpid") == "env"


def test_keys_filepath_env_var_missing_no_fallback(tmp_path, monkeypatch):
    # 环境变量指向的文件不存在：严格报错，不回退探测
    monkeypatch.chdir(tmp_path)
    missing = tmp_path / "nope.ini"
    monkeypatch.setenv("PTEN_KEYS_FILE", str(missing))

    keys = Keys()
    assert keys.keys_filepath == missing
    with pytest.raises(FileNotFoundError):
        keys.get_key("ww", "corpid")


def test_keys_filepath_env_var_empty_treated_as_unset(tmp_path, monkeypatch):
    # PTEN_KEYS_FILE 为空串时视为未设置，继续探测当前目录
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    _write_keys_ini(cwd / "pten_keys.ini", corpid="cwd")
    monkeypatch.setenv("PTEN_KEYS_FILE", "")

    keys = Keys()
    assert keys.get_key("ww", "corpid") == "cwd"


def test_keys_filepath_tilde_expanded(tmp_path, monkeypatch):
    # 显式路径与环境变量里的 ~ 展开为用户主目录
    home = tmp_path / "home"
    (home / ".pten").mkdir(parents=True)
    _write_keys_ini(home / ".pten" / "pten_keys.ini", corpid="home")
    _patch_home(monkeypatch, home)

    monkeypatch.setenv("PTEN_KEYS_FILE", "~/.pten/pten_keys.ini")
    keys = Keys()
    assert keys.get_key("ww", "corpid") == "home"

    keys = Keys("~/.pten/pten_keys.ini")
    assert keys.get_key("ww", "corpid") == "home"


def test_keys_filepath_cwd_beats_home(tmp_path, monkeypatch):
    # 当前目录的 pten_keys.ini 优先于 ~/.pten/pten_keys.ini
    _setup_lookup_dirs(tmp_path, monkeypatch)

    keys = Keys()
    assert keys.get_key("ww", "corpid") == "cwd"


def test_keys_filepath_home_fallback(tmp_path, monkeypatch):
    # 当前目录没有时回退到 ~/.pten/pten_keys.ini
    home = _setup_lookup_dirs(tmp_path, monkeypatch, cwd_keys=False)

    keys = Keys()
    assert keys.get_key("ww", "corpid") == "home"
    # token 缓存文件与 keys 文件同目录
    assert keys.TOKEN_PATH == home / ".pten" / "pten_token.json"


def test_keys_filepath_home_unavailable_falls_back_to_cwd(tmp_path, monkeypatch):
    # 无主目录（如容器以无 passwd 条目的 UID 运行）时 Path.home() 抛 RuntimeError，
    # 不应击穿当前目录回退——cwd 有 keys 文件时应正常命中
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    _write_keys_ini(cwd / "pten_keys.ini", corpid="cwd")
    monkeypatch.delenv("PTEN_KEYS_FILE", raising=False)

    def _no_home():
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", _no_home)

    keys = Keys()
    assert keys.get_key("ww", "corpid") == "cwd"


def test_keys_filepath_all_missing(tmp_path, monkeypatch):
    # 四个来源都没有时回落到 ./pten_keys.ini（旧行为），取 key 时报 FileNotFoundError
    _setup_lookup_dirs(tmp_path, monkeypatch, cwd_keys=False, home_keys=False)

    keys = Keys()
    assert keys.keys_filepath == Path("pten_keys.ini")
    assert keys.TOKEN_PATH == Path("pten_token.json")
    with pytest.raises(FileNotFoundError):
        keys.get_key("ww", "corpid")


def test_token_path_follows_keys_file_dir(tmp_path):
    # token 缓存文件跟随 keys 文件所在目录，实际写入也落在该目录
    ini = tmp_path / "sub" / "keys.ini"
    ini.parent.mkdir()
    _write_keys_ini(ini, corpid="x")
    keys = Keys(str(ini))
    assert keys.TOKEN_PATH == tmp_path / "sub" / "pten_token.json"

    keys.save_access_token("ww_x", "token")
    assert (tmp_path / "sub" / "pten_token.json").is_file()


def test_save_token_cache_write_failure_not_fatal(tmp_path):
    # token 缓存写入失败（如 keys 文件所在目录只读）时仅告警不抛异常，内存缓存不受影响
    ini = tmp_path / "keys.ini"
    _write_keys_ini(ini)
    keys = Keys(str(ini))
    keys.TOKEN_PATH = tmp_path  # 目录不可作为文件写入，模拟只读目录

    keys.save_access_token("ww_x", "token")
    assert keys.access_tokens["ww_x"]["access_token"] == "token"


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
