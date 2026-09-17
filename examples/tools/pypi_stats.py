"""PyPI 包下载量查询示例（数据来自 pypistats.org）。

运行前提：无需任何配置（pypistats.org 不需要鉴权）。
注意：pypistats.org 按 IP 全站限流，频繁运行会触发 429；
PypiStats 已内置退避重试（默认等待 30/90 秒、最多 3 次尝试）。
运行方式：python examples/tools/pypi_stats.py [包名]
"""

import sys

from pten.tools import PypiStats

if __name__ == "__main__":
    package = sys.argv[1] if len(sys.argv) > 1 else "pten"

    stats = PypiStats(package)

    print(f"包名: {package}")
    print(f"最近一周: {stats.week_downloads()}")
    print(f"最近一个月: {stats.month_downloads()}")
    print(f"最近180天下载量: {stats.last_180_days_downloads()}")
