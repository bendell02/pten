import pytest
import requests

from pten.tools.pypi_stats import PypiStats


def _make_response(mocker, status_code=200, payload=None):
    """构造 mock HTTP 响应：raise_for_status 按 status_code 决定是否抛错，json() 返回 payload"""
    resp = mocker.Mock(status_code=status_code)
    resp.json.return_value = payload
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(
            f"{status_code} Error", response=resp
        )
    return resp


def _make_stats(mocker, responses):
    """构造 PypiStats：session.get 按序返回 responses，重试退避的 sleep 被 mock 掉。

    返回 (stats, sleep_mock)。
    """
    stats = PypiStats("pten", retries=3, backoff=(30, 90))
    mocker.patch.object(stats.session, "get", side_effect=responses)
    sleep_mock = mocker.patch("pten.tools.pypi_stats.time.sleep")
    return stats, sleep_mock


def test_week_and_month_share_one_request(mocker):
    """周、月下载量同源于 /recent，缓存生效时两个方法只发一次请求"""
    stats, _ = _make_stats(
        mocker,
        [
            _make_response(
                mocker, payload={"data": {"last_week": 284, "last_month": 734}}
            )
        ],
    )

    assert stats.week_downloads() == 284
    assert stats.month_downloads() == 734
    assert stats.session.get.call_count == 1
    assert stats.session.get.call_args.args[0] == (
        "https://pypistats.org/api/packages/pten/recent"
    )


def test_last_180_days_downloads_sums_without_mirrors(mocker):
    """180 天求和只统计 without_mirrors 类目（镜像流量剔除）"""
    payload = {
        "data": [
            {"date": "2026-09-10", "category": "without_mirrors", "downloads": 40},
            {"date": "2026-09-10", "category": "with_mirrors", "downloads": 60},
            {"date": "2026-09-11", "category": "without_mirrors", "downloads": 50},
        ]
    }
    stats, _ = _make_stats(mocker, [_make_response(mocker, payload=payload)])

    assert stats.last_180_days_downloads() == 90


def test_retry_on_rate_limit(mocker):
    """429 限流属于可重试失败：按 backoff 退避后重试，第二次成功"""
    stats, sleep_mock = _make_stats(
        mocker,
        [
            _make_response(mocker, status_code=429),
            _make_response(mocker, payload={"data": {"last_week": 1, "last_month": 2}}),
        ],
    )

    assert stats.week_downloads() == 1
    assert stats.session.get.call_count == 2
    sleep_mock.assert_called_once_with(30)


def test_retry_on_invalid_json(mocker):
    """200 但 body 非 JSON（限流页 / 网关页）同样按可重试失败处理"""
    bad = _make_response(mocker, payload={"data": {}})
    bad.json.side_effect = ValueError("Expecting value: line 1 column 1")
    stats, _ = _make_stats(
        mocker,
        [
            bad,
            _make_response(mocker, payload={"data": {"last_week": 3, "last_month": 4}}),
        ],
    )

    assert stats.week_downloads() == 3


def test_client_error_raises_without_retry(mocker):
    """429 之外的 4xx（如包名拼错的 404）是确定性失败，不重试直接抛出"""
    stats, sleep_mock = _make_stats(mocker, [_make_response(mocker, status_code=404)])

    with pytest.raises(requests.HTTPError):
        stats.week_downloads()
    assert stats.session.get.call_count == 1
    sleep_mock.assert_not_called()


def test_cache_expires_after_ttl(mocker):
    """缓存超过 cache_ttl 后下次访问重新请求，不返回陈旧数据"""
    stats, _ = _make_stats(
        mocker,
        [
            _make_response(
                mocker, payload={"data": {"last_week": 284, "last_month": 734}}
            ),
            _make_response(
                mocker, payload={"data": {"last_week": 300, "last_month": 800}}
            ),
        ],
    )
    assert stats.week_downloads() == 284
    assert stats.session.get.call_count == 1

    # 把缓存时间戳拨到 2 小时前，模拟过期（默认 cache_ttl=3600）
    stats._recent_fetched_at -= 7200
    assert stats.week_downloads() == 300
    assert stats.session.get.call_count == 2


def test_exhausted_retries_raises(mocker):
    """持续 429 且重试用尽时抛出最后一次异常，退避只发生在失败等待处"""
    stats, sleep_mock = _make_stats(
        mocker, [_make_response(mocker, status_code=429)] * 3
    )

    with pytest.raises(requests.HTTPError):
        stats.week_downloads()
    assert stats.session.get.call_count == 3
    assert sleep_mock.call_args_list == [mocker.call(30), mocker.call(90)]
