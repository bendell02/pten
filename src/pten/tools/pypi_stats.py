"""
pten.tools.pypi_stats
~~~~~~~~~~~~~~~~~~~~~

PyPI 包下载量查询，数据来自 pypistats.org。
"""

import time

import requests

from .. import logger


class PypiStats:
    """输入包名，查询周 / 月 / 最近180天下载量

    pypistats.org 按 IP 全站限流，超限返回 429 且 body 是一段 HTML 而非 JSON，
    直接 .json() 会抛 JSONDecodeError("Expecting value: line 1 column 1")，
    因此请求统一走 _get_json：先检查状态码再解析，失败时退避重试
    （限流窗口实测几分钟内恢复）。

    :param package: PyPI 包名，如 "pten"
    :param timeout: 单次请求超时秒数
    :param retries: 含首次请求在内的总尝试次数
    :param backoff: 每次重试前的等待秒数序列；长度不足时末档兜底（按最后一个值持续等待），空序列退化为不等候
    :param cache_ttl: 响应缓存有效期秒数，超过后下次访问重新请求；默认 3600（1 小时）
    """

    BASE_URL = "https://pypistats.org/api/packages"

    def __init__(
        self, package, timeout=30, retries=3, backoff=(30, 90), cache_ttl=3600
    ):
        self.package = package
        self.timeout = timeout
        self.retries = max(retries, 1)  # 含首次请求在内的总尝试次数
        self.backoff = backoff or (0,)
        self.cache_ttl = cache_ttl  # 响应缓存有效期秒数
        self.session = requests.Session()
        self._recent_data = None
        self._recent_fetched_at = None
        self._overall_data = None
        self._overall_fetched_at = None

    def _get_json(self, url):
        """带超时和重试的 GET；429/5xx/超时/空响应时退避重试，仍失败则抛出明确的异常"""
        for attempt in range(self.retries):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                resp = getattr(exc, "response", None)
                # 429 限流之外的 4xx 是确定性失败（如包名拼错 404），重试没有意义
                if (
                    resp is not None
                    and 400 <= resp.status_code < 500
                    and resp.status_code != 429
                ):
                    raise
                if attempt == self.retries - 1:
                    raise
                wait = self.backoff[min(attempt, len(self.backoff) - 1)]
                msg = f"请求失败（{exc}），{wait} 秒后重试 ({attempt + 1}/{self.retries - 1})..."
                logger.warning(msg)
                time.sleep(wait)

    def _cache_stale(self, fetched_at):
        """缓存是否需要重新拉取：从未填充，或距上次拉取已超过 cache_ttl 秒"""
        return fetched_at is None or time.time() - fetched_at > self.cache_ttl

    def _recent(self):
        """GET /recent 的 data；周、月下载量同源，缓存后两个方法只发一次请求"""
        if self._cache_stale(self._recent_fetched_at):
            self._recent_data = self._get_json(
                f"{self.BASE_URL}/{self.package}/recent"
            )["data"]
            self._recent_fetched_at = time.time()
        return self._recent_data

    def _overall(self):
        """GET /overall 的 data（日下载量明细，pypistats 仅保留约 180 天）"""
        if self._cache_stale(self._overall_fetched_at):
            self._overall_data = self._get_json(
                f"{self.BASE_URL}/{self.package}/overall"
            )["data"]
            self._overall_fetched_at = time.time()
        return self._overall_data

    def week_downloads(self):
        """最近一周下载量"""
        return self._recent()["last_week"]

    def month_downloads(self):
        """最近一月下载量"""
        return self._recent()["last_month"]

    def last_180_days_downloads(self):
        """最近180天下载量总和

        pypistats 的 overall 数据可能缺天（缺的天整行不存在），
        有数据天数不足 180 时总和偏小，与历史记录不可比。
        """
        rows = [
            item for item in self._overall() if item["category"] == "without_mirrors"
        ]
        return sum(item["downloads"] for item in rows)

    def close(self):
        """关闭底层 requests.Session，释放连接池"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
