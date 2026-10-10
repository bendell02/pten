"""pten.tools.jev 的 mock 测试：配置解析、代理注入、ask 透传、环境变量回退。

不访问真实 API：TypeSafeClient / httpx2 全部 mock，配置用 tmp_path 下的临时 ini。
"""

import configparser
import logging

import pytest
from typesafe_sdk.constants import DEFAULT_TIMEOUT

from pten.tools import jev
from pten.tools.jev import Jev, Noul


@pytest.fixture(autouse=True)
def clean_typesafe_env(monkeypatch):
    """清理 TYPESAFE_* 环境变量，避免宿主机配置影响用例"""
    for name in ("TYPESAFE_API_KEY", "TYPESAFE_BASE_URL", "TYPESAFE_DEFAULT_MODEL"):
        monkeypatch.delenv(name, raising=False)


def write_ini(tmp_path, content):
    ini = tmp_path / "keys.ini"
    ini.write_text(content, encoding="utf-8")
    return str(ini)


# ---------------------------------------------------------------------------
# api_key / base_url / model 的解析顺序：显式参数 > [jev] 段 > 默认（None 透传 SDK）
# ---------------------------------------------------------------------------
def test_explicit_params_win_over_config(mocker, tmp_path):
    ini = write_ini(
        tmp_path,
        "[jev]\napi_key=apikey-ini\nbase_url=https://ini.example.com\nmodel=jev-ini\n",
    )
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")

    Jev(
        api_key="apikey-explicit",
        base_url="https://explicit.example.com",
        model="jev-explicit",
        keys_filepath=ini,
    )

    mock_client.assert_called_once_with(
        api_key="apikey-explicit",
        base_url="https://explicit.example.com",
        model="jev-explicit",
        http_client=None,
    )


def test_config_from_jev_section(mocker, tmp_path):
    ini = write_ini(
        tmp_path,
        "[jev]\napi_key=apikey-ini\nbase_url=https://ini.example.com\nmodel=jev-ini\n",
    )
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")
    mock_httpx2 = mocker.patch("pten.tools.jev.httpx2")

    Jev(keys_filepath=ini)

    mock_client.assert_called_once_with(
        api_key="apikey-ini",
        base_url="https://ini.example.com",
        model="jev-ini",
        http_client=None,
    )
    mock_httpx2.Client.assert_not_called()  # 无代理配置时不建 httpx2 客户端


def test_sdk_defaults_when_unconfigured(mocker, tmp_path):
    # [jev] 段只配 api_key，base_url/model 传 None 让 SDK 用默认值
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\n")
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")

    Jev(keys_filepath=ini)

    kwargs = mock_client.call_args.kwargs
    assert kwargs["api_key"] == "apikey-ini"
    assert kwargs["base_url"] is None  # SDK 默认 https://api.typesafe.ai
    assert kwargs["model"] is None  # SDK 默认 jev-latest


def test_api_key_from_env(mocker, tmp_path, monkeypatch):
    ini = write_ini(tmp_path, "[globals]\n")  # 无 [jev] 段
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")
    monkeypatch.setenv("TYPESAFE_API_KEY", "apikey-env")

    Jev(keys_filepath=ini)
    assert mock_client.call_args.kwargs["api_key"] == "apikey-env"


def test_jev_section_beats_env(mocker, tmp_path, monkeypatch):
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\n")
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")
    monkeypatch.setenv("TYPESAFE_API_KEY", "apikey-env")

    Jev(keys_filepath=ini)
    assert mock_client.call_args.kwargs["api_key"] == "apikey-ini"


def test_missing_api_key_raises(mocker, tmp_path):
    ini = write_ini(tmp_path, "[globals]\n")
    mocker.patch("pten.tools.jev.TypeSafeClient")

    with pytest.raises(ValueError) as exc:
        Jev(keys_filepath=ini)

    msg = str(exc.value)
    assert "api_key" in msg
    assert "[jev]" in msg  # 提示配置途径
    assert "TYPESAFE_API_KEY" in msg  # 提示环境变量途径


def test_missing_api_key_missing_file_hint(tmp_path):
    # 配置文件不存在时报错应提示文件缺失，方便定位
    missing = tmp_path / "nope.ini"
    with pytest.raises(ValueError) as exc:
        Jev(keys_filepath=str(missing))
    msg = str(exc.value)
    assert "nope.ini" in msg
    assert "不存在" in msg


# ---------------------------------------------------------------------------
# 代理解析顺序：显式参数 > [jev] proxy > [proxies] 段（先 https 后 http 键）
# ---------------------------------------------------------------------------
PROXIES_INI = (
    "[jev]\napi_key=apikey-ini\n"
    "[proxies]\nhttp=http://p-http:8888\nhttps=http://p-https:8888\n"
)


def test_proxy_from_jev_section(mocker, tmp_path):
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\nproxy=http://p-jev:1080\n")
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")
    mock_httpx2 = mocker.patch("pten.tools.jev.httpx2")

    Jev(keys_filepath=ini)

    mock_httpx2.Client.assert_called_once_with(
        proxy="http://p-jev:1080", timeout=DEFAULT_TIMEOUT
    )
    assert (
        mock_client.call_args.kwargs["http_client"] is mock_httpx2.Client.return_value
    )


def test_proxy_client_uses_sdk_default_timeout(mocker, tmp_path):
    # SDK 会继承注入客户端的 timeout 当请求超时，不传则落到 httpx2 默认 5s，
    # 使代理路径（延迟最高）反而比直连（SDK 默认 10s）更容易超时
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\nproxy=http://p-jev:1080\n")
    mocker.patch("pten.tools.jev.TypeSafeClient")
    mock_httpx2 = mocker.patch("pten.tools.jev.httpx2")

    Jev(keys_filepath=ini)

    kwargs = mock_httpx2.Client.call_args.kwargs
    assert kwargs["timeout"] is DEFAULT_TIMEOUT  # 与直连路径的 SDK 默认一致


def test_proxy_log_masks_embedded_credentials(mocker, tmp_path, caplog):
    # 代理地址可能内嵌 user:pass，写日志前应屏蔽，避免凭证落盘
    proxy_url = "http://user:secret@p-jev:1080"
    ini = write_ini(tmp_path, f"[jev]\napi_key=apikey-ini\nproxy={proxy_url}\n")
    mocker.patch("pten.tools.jev.TypeSafeClient")
    mocker.patch("pten.tools.jev.httpx2")

    with caplog.at_level(logging.INFO, logger="pten"):
        Jev(keys_filepath=ini)

    assert "secret" not in caplog.text
    assert "user:secret" not in caplog.text
    assert "http://***@p-jev:1080" in caplog.text


def test_proxy_log_masks_password_with_at(mocker, tmp_path, caplog):
    # 密码含未转义 @ 时（合法 URL，userinfo 以最后一个 @ 结束），
    # 屏蔽须覆盖到最后一个 @，不能漏出密码片段
    proxy_url = "http://user:p@ss@p-jev:1080"
    ini = write_ini(tmp_path, f"[jev]\napi_key=apikey-ini\nproxy={proxy_url}\n")
    mocker.patch("pten.tools.jev.TypeSafeClient")
    mocker.patch("pten.tools.jev.httpx2")

    with caplog.at_level(logging.INFO, logger="pten"):
        Jev(keys_filepath=ini)

    assert "p@ss" not in caplog.text
    assert "ss@p-jev" not in caplog.text  # 现状 bug 就漏在这里
    assert "http://***@p-jev:1080" in caplog.text


def test_proxy_jev_section_beats_proxies_section(mocker, tmp_path):
    ini = write_ini(
        tmp_path,
        "[jev]\napi_key=apikey-ini\nproxy=http://p-jev:1080\n"
        "[proxies]\nhttp=http://p-http:8888\nhttps=http://p-https:8888\n",
    )
    mocker.patch("pten.tools.jev.TypeSafeClient")
    mock_httpx2 = mocker.patch("pten.tools.jev.httpx2")

    Jev(keys_filepath=ini)

    mock_httpx2.Client.assert_called_once_with(
        proxy="http://p-jev:1080", timeout=DEFAULT_TIMEOUT
    )


def test_proxy_fallback_proxies_https(mocker, tmp_path):
    ini = write_ini(tmp_path, PROXIES_INI)
    mocker.patch("pten.tools.jev.TypeSafeClient")
    mock_httpx2 = mocker.patch("pten.tools.jev.httpx2")

    Jev(keys_filepath=ini)

    # [proxies] 同时配了 http/https 时优先 https
    mock_httpx2.Client.assert_called_once_with(
        proxy="http://p-https:8888", timeout=DEFAULT_TIMEOUT
    )


def test_proxy_fallback_proxies_http_only(mocker, tmp_path):
    ini = write_ini(
        tmp_path, "[jev]\napi_key=apikey-ini\n[proxies]\nhttp=http://p-http:8888\n"
    )
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")
    mock_httpx2 = mocker.patch("pten.tools.jev.httpx2")

    Jev(keys_filepath=ini)

    # 只配 http 键时用它兜底（httpx2 已被 mock，代理字符串原样传给 Client）
    kwargs = mock_client.call_args.kwargs
    assert kwargs["http_client"] is mock_httpx2.Client.return_value
    mock_httpx2.Client.assert_called_once_with(
        proxy="http://p-http:8888", timeout=DEFAULT_TIMEOUT
    )


def test_explicit_proxy_beats_all(mocker, tmp_path):
    ini = write_ini(
        tmp_path,
        "[jev]\napi_key=apikey-ini\nproxy=http://p-jev:1080\n"
        "[proxies]\nhttps=http://p-https:8888\n",
    )
    mocker.patch("pten.tools.jev.TypeSafeClient")
    mock_httpx2 = mocker.patch("pten.tools.jev.httpx2")

    Jev(api_key="apikey-ini", proxy="http://p-explicit:1080", keys_filepath=ini)

    mock_httpx2.Client.assert_called_once_with(
        proxy="http://p-explicit:1080", timeout=DEFAULT_TIMEOUT
    )


def test_no_proxy_no_http_client(mocker, tmp_path):
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\n")
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")
    mock_httpx2 = mocker.patch("pten.tools.jev.httpx2")

    Jev(keys_filepath=ini)

    assert mock_client.call_args.kwargs["http_client"] is None
    mock_httpx2.Client.assert_not_called()


def test_sdk_client_failure_closes_proxy_client(mocker, tmp_path):
    # SDK 构造会校验 api_key 格式，失败时应关闭已建的代理客户端再原样抛出
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\nproxy=http://p-jev:1080\n")
    mocker.patch(
        "pten.tools.jev.TypeSafeClient", side_effect=ValueError("invalid api_key")
    )
    mock_httpx2 = mocker.patch("pten.tools.jev.httpx2")

    with pytest.raises(ValueError, match="invalid api_key"):
        Jev(keys_filepath=ini)

    mock_httpx2.Client.return_value.close.assert_called_once()


# ---------------------------------------------------------------------------
# ask / close / 上下文管理器
# ---------------------------------------------------------------------------
def test_ask_passes_through_and_returns(mocker, tmp_path):
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\nmodel=jev-ini\n")
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")
    j = Jev(keys_filepath=ini)

    questions = {"is_billing": Noul(instructions="Is this about billing?")}
    result = j.ask("I was charged twice", questions, model="jev-1.13")

    mock_client.return_value.system_one.assert_called_once_with(
        "I was charged twice", questions, model="jev-1.13"
    )
    assert result is mock_client.return_value.system_one.return_value


def test_ask_log_reflects_per_call_model(mocker, tmp_path, caplog):
    # 逐调用的 model 覆盖（docstring 支持的 kwargs）应体现在日志里
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\nmodel=jev-ini\n")
    mocker.patch("pten.tools.jev.TypeSafeClient")
    j = Jev(keys_filepath=ini)

    questions = {"is_billing": Noul(instructions="Is this about billing?")}
    with caplog.at_level(logging.INFO, logger="pten"):
        j.ask("I was charged twice", questions, model="jev-1.13")

    assert "model=jev-1.13" in caplog.text


def test_ask_log_marks_sdk_default_model(mocker, tmp_path, caplog):
    # 配置链任何一级都没有 model 时，日志应如实标注 SDK 默认，
    # 而不是硬编码一个可能随 SDK 演进过期/被环境变量改变的模型名
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\n")
    mocker.patch("pten.tools.jev.TypeSafeClient")
    j = Jev(keys_filepath=ini)

    questions = {"is_billing": Noul(instructions="Is this about billing?")}
    with caplog.at_level(logging.INFO, logger="pten"):
        j.ask("I was charged twice", questions)

    assert "model=(SDK 默认)" in caplog.text


def test_ask_with_dict_state(mocker, tmp_path):
    # state 允许 dict（JSONContent），问原样透传给 system_one
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\n")
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")
    j = Jev(keys_filepath=ini)

    state = {"document": "I was charged twice"}
    questions = {"is_billing": Noul(instructions="About billing?")}
    j.ask(state, questions)

    mock_client.return_value.system_one.assert_called_once_with(state, questions)


def test_close_and_context_manager(mocker, tmp_path):
    ini = write_ini(tmp_path, "[jev]\napi_key=apikey-ini\n")
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")

    j = Jev(keys_filepath=ini)
    j.close()
    assert mock_client.return_value.close.call_count == 1

    with Jev(keys_filepath=ini) as ctx:
        assert isinstance(ctx, Jev)
    assert mock_client.return_value.close.call_count == 2  # with 退出时再关一次


# ---------------------------------------------------------------------------
# Keys 注入与符号再导出
# ---------------------------------------------------------------------------
def test_keys_injection(mocker):
    # 传入共享 Keys 实例时配置应从它读取，而不是自建 Keys
    mock_client = mocker.patch("pten.tools.jev.TypeSafeClient")
    mock_keys = mocker.MagicMock()

    def fake_get_key(section, option):
        if (section, option) == ("jev", "model"):
            return "jev-injected"
        raise configparser.Error("no such option")

    mock_keys.get_key.side_effect = fake_get_key

    Jev(api_key="apikey-ini", keys=mock_keys)

    assert mock_client.call_args.kwargs["model"] == "jev-injected"


def test_reexport_primitives():
    # Choice/Score/Noul 应可从 pten.tools.jev 直接导入（单一 import 站点）
    from typesafe_sdk import Choice as SdkChoice
    from typesafe_sdk import Noul as SdkNoul
    from typesafe_sdk import Score as SdkScore

    assert jev.Choice is SdkChoice
    assert jev.Score is SdkScore
    assert jev.Noul is SdkNoul
