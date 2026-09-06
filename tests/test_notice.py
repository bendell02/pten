from pten.notice import Birthday, Deepseek, LLM, Weather
import pytest


def test_deepseek(mocker):
    mock_get = mocker.patch("pten.notice.Deepseek.get_completion")
    mock_get.return_value = "newton"

    deepseek = Deepseek("pten_keys_example.ini")
    content = deepseek.get_completion("简略介绍一下牛顿")
    assert content != ""


def test_llm(mocker):
    mock_get = mocker.patch("pten.notice.LLM.get_completion")
    mock_get.return_value = "newton"

    llm = LLM(
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        model="deepseek-v4-flash",
        keys_filepath="pten_keys_example.ini",
    )
    content = llm.get_completion("简略介绍一下牛顿")
    assert content != ""


def test_llm_provider(tmp_path):
    # 命名 provider：从 [llm:openai] 段读取配置
    ini = tmp_path / "keys.ini"
    ini.write_text(
        "[llm:openai]\n"
        "base_url=https://api.openai.com/v1\n"
        "api_key=sk-test\n"
        "model=gpt-4o-mini\n",
        encoding="utf-8",
    )
    llm = LLM(provider="openai", keys_filepath=str(ini))
    assert llm.base_url == "https://api.openai.com/v1"
    assert llm.api_key == "sk-test"
    assert llm.model == "gpt-4o-mini"
    assert llm.system_prompt == "You are a helpful assistant"


def test_llm_provider_explicit_override(tmp_path):
    # 显式传入的参数优先于 [llm:*] 配置
    ini = tmp_path / "keys.ini"
    ini.write_text(
        "[llm:openai]\n"
        "base_url=https://api.openai.com/v1\n"
        "api_key=sk-test\n"
        "model=gpt-4o-mini\n",
        encoding="utf-8",
    )
    llm = LLM(provider="openai", model="gpt-4o", keys_filepath=str(ini))
    assert llm.model == "gpt-4o"  # 显式传入优先
    assert llm.base_url == "https://api.openai.com/v1"  # 来自配置


def test_llm_provider_incomplete_raises(tmp_path):
    # [llm:*] 段缺 api_key/model 时应抛 ValueError
    ini = tmp_path / "keys.ini"
    ini.write_text(
        "[llm:openai]\nbase_url=https://api.openai.com/v1\n", encoding="utf-8"
    )
    with pytest.raises(ValueError):
        LLM(provider="openai", keys_filepath=str(ini))


def test_llm_provider_unknown_raises(tmp_path):
    # provider 名未配置：报错并列出可用 provider，确认 list_llm_providers 被使用
    ini = tmp_path / "keys.ini"
    ini.write_text(
        "[llm:deepseek]\nbase_url=x\napi_key=y\nmodel=z\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as exc:
        LLM(provider="openai", keys_filepath=str(ini))
    msg = str(exc.value)
    assert "openai" in msg  # 请求的 provider 名
    assert "deepseek" in msg  # 列出的可用 provider


def test_llm_provider_missing_keys_file_raises(tmp_path):
    # 配置文件不存在：报错应提示文件缺失，而不只是"可用 provider: []"
    missing = tmp_path / "nope.ini"
    with pytest.raises(ValueError) as exc:
        LLM(provider="openai", keys_filepath=str(missing))
    msg = str(exc.value)
    assert "nope.ini" in msg
    assert "不存在" in msg


def test_llm_unknown_kwarg_raises():
    # 收紧签名后，拼写错误的参数应立即报 TypeError，而不是被 **kwargs 静默忽略
    with pytest.raises(TypeError):
        LLM(base_urll="https://api.openai.com/v1", api_key="sk-x", model="gpt-4o-mini")


def test_llm_default_from_notice(tmp_path):
    # 不传 provider：向后兼容，读 [notice] 的 llm_* 键
    ini = tmp_path / "keys.ini"
    ini.write_text(
        "[notice]\n"
        "llm_base_url=https://api.deepseek.com\n"
        "llm_api_key=sk-test\n"
        "llm_model=deepseek-v4-flash\n",
        encoding="utf-8",
    )
    llm = LLM(keys_filepath=str(ini))
    assert llm.base_url == "https://api.deepseek.com"
    assert llm.api_key == "sk-test"
    assert llm.model == "deepseek-v4-flash"
    assert llm.system_prompt == "You are a helpful assistant"


def test_weather(mocker):
    mock_get = mocker.patch("pten.notice.Weather.get_city_weather")
    mock_get.return_value = "good weather"

    weather = Weather("pten_keys_example.ini")
    weather_str = weather.get_city_weather("深圳", "Shenzhen")
    assert weather_str != ""


def test_birthday_leap_month():
    assert Birthday.is_leap_month(2020, 4) is True
    assert Birthday.is_leap_month(2019, 4) is False
