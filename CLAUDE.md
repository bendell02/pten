# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`pten` is a Python library (src-layout, `src/pten/`) for calling WeChat Work (企业微信) APIs — bot/app messaging, contacts, documents, callback crypto — plus a small set of "notice" helpers (birthday reminders, weather, DeepSeek). A Feishu (飞书) bot path (`fs_api`/`fs_messager`) is being added on the `add_feishu` branch.

## Commands

```bash
# Install editable (pulls deps: apscheduler, lunardate, openai, pycryptodome)
pip install -e .
# Test deps
pip install "pytest>=3" "pytest-mock>=3"

# Run all tests from the repo root (conftest.py adds src/ to sys.path, so no install needed)
pytest

# Run a single test / file / by keyword
pytest tests/test_keys.py
pytest tests/test_wwmessager.py::test_app_msg_sender
pytest tests/test_wwapi.py -k jsapi
```

Tests run from the repo root by default. `Keys`, the token cache (`pten_token.json`), and the log file (`pten.log`) are all resolved relative to the CWD, so running elsewhere breaks them.

### Real-API tests

Most tests mock `requests.get`/`requests.post` via `pytest-mock`'s `mocker` fixture and use `pten_keys_example.ini`. A few (`test_*_real_key`, the birthday scheduler test, `wwcrypt`'s `VerifyURL`/`DecryptMsg`) hit live APIs and are gated behind flags in `tests/conftest.py`:

- `use_real_keys = True` — switches `key_filepath_example` to the real `pten_keys.ini` and unskips live tests.
- `enable_long_time_tests = True` — unskips the long-running `BlockingScheduler` birthday test.

## Architecture

### Config & state — `keys.py`
`Keys` is the single config dependency every other module takes. It reads `pten_keys.ini` (`configparser`, sections `ww` / `fs` / `globals` / `proxies` / `notice`) and owns token/ticket caching: access tokens and corp/app jsapi tickets are persisted to `pten_token.json` keyed by `sha1(corpid+corpsecret)`, with a 7200s expiry and in-memory cache. Public classes accept `keys_filepath="pten_keys.ini"` plus an optional `keys: Keys` so a shared `Keys` instance (and its token cache) can be injected across modules.

### Shared plumbing — `base_api.py`
`base_api.AbstractApi` owns the HTTP machinery used by both WeChat Work and Feishu: `http_call` dispatch (POST/GET/POST_FILE), URL building (`_make_url`, `_append_args`), token substitution (`_append_token`), response checking (`_check_response` → raises `ApiException` unless the success code is `0`), and token-expiry retry (up to 3 times). Each vendor module subclasses it and sets class attributes: `BASE_URL`; `RESPONSE_CODE_FIELD`/`RESPONSE_MSG_FIELD` (`errcode`/`errmsg` for WW, `code`/`msg` for Feishu); `TOKEN_PLACEHOLDERS` — ordered `(placeholder, getter_name)` tuples where longer/specific placeholders must come first (e.g. `SUITE_ACCESS_TOKEN` before `ACCESS_TOKEN`, since the former contains the latter; `_append_token`/`_refresh_token` use the first match); and `TOKEN_EXPIRED_CODES` (empty for Feishu, so refresh is a no-op). A `_debug_url` hook lets WW append `&debug=1` in debug mode.

### API layer — `wwapi.py` (WeChat Work)
`AbstractApi` is a config subclass of `base_api.AbstractApi`: `BASE_URL=https://qyapi.weixin.qq.com`, `errcode`/`errmsg` response fields, all four token placeholders, and `TOKEN_EXPIRED_CODES=(40014,42001,42007,42009)`. Endpoint definitions live in module-level dicts (`BOT_API_TYPE`, `CORP_API_TYPE`, `SERVICE_CORP_API_TYPE`, `SERVICE_PROVIDER_API_TYPE`) mapping a logical name → `[shortUrl, method]`. URLs carry placeholders (`ACCESS_TOKEN`, `WEBHOOK_KEY`, `SUITE_ACCESS_TOKEN`, `PROVIDER_ACCESS_TOKEN`) that `_append_token` substitutes lazily by calling the subclass's `get_*` method; `_refresh_token` calls the matching `refresh_*` on token-expired errcodes and retries up to 3 times. `_check_response` raises `ApiException(errcode, errmsg)` unless `errcode == 0`. Subclasses: `BotApi` (webhook only), `CorpApi` (access_token + jsapi tickets), `ServiceCorpApi`, `ServiceProviderApi`.

### Feishu layer — `fs_api.py` / `fs_messager.py`
`AbstractApi` is a config subclass of `base_api.AbstractApi`: `BASE_URL=https://open.feishu.cn/open-apis`, `code`/`msg` response fields, webhook-only (`WEBHOOK_KEY` placeholder), and `TOKEN_EXPIRED_CODES=()` so refresh is a no-op (real Feishu token refresh not yet implemented). Otherwise minimal: webhook-only, POST-only, response success is `code == 0` / `msg == "ok"` (not `errcode`/`errmsg`). Because the HTTP plumbing is shared via `base_api`, extending Feishu support now mirrors WeChat Work automatically — just add endpoint entries to `fs_api.BOT_API_TYPE` and thin methods on the sender.

### High-level modules
- `wwmessager.py` — `MsgSender` base; `BotMsgSender` (webhook, self-throttles to 20 msg/min via a `Queue`) and `AppMsgSender` (access_token, routes to `message/send` or `appchat/send`, resolves `touser`/`toparty`/`totag` defaulting to `@all`). Media uploads go through `_get_media_id`.
- `wwcontact.py` — `Contact` wraps `CorpApi` using `contact_sync_secret` (from `[ww]`, or passed in) instead of `app_secret`.
- `wwdoc.py` — `Doc` wraps `CorpApi` for wedoc / smartsheet / form endpoints.
- `wwcrypt.py` — `WXBizMsgCrypt` (VerifyURL / DecryptMsg / EncryptMsg) for callback message crypto. Vendored from `weworkapi_python`.
- `notice.py` — `Notice` base (default `report_func=print`); `Birthday` (lunar via `lunardate` + solar, schedules via `apscheduler` and auto-reschedules the next year, handles leap months); `Deepseek` (OpenAI client pointed at the DeepSeek base_url); `Weather` (seniverse API).

### Logging
Importing `pten` (i.e. `from . import logger` in each module) runs `src/pten/__init__.py`, which configures a named `logger` with a colored console handler and a 30MB-rotating `pten.log` file handler. Use this `logger`, not `print`, inside the package.

## Conventions

- **New API endpoint?** Add an entry to the relevant `*_API_TYPE` dict in `wwapi.py` (or `fs_api.py`), then expose it as a thin method on the high-level class (`Contact`, `Doc`, sender, etc.) that builds the `data` dict and calls `self.api.http_call(...)`. Keep the data-shape and doc-link comment style of neighboring methods.
- **Response assertions in tests:** WeChat Work → `assert_response` (checks `errcode==0`, `errmsg=="ok"`); Feishu → `assert_fs_response` (checks `code==0`, `msg=="ok"`). Both live in `tests/conftest.py`.
- **`pten_keys.ini` and `pten_token.json` are gitignored** (real secrets / cached tokens). `pten_keys_example.ini` is the committed, fake-credentials fixture used by mocked tests.
