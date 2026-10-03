"""
pten.utils
~~~~~~~~~~~~~~~~

公共工具函数，供包内各模块共享（区别于 tools/ 子包的对外工具）。
"""

import json
from typing import Optional


def brief_for_log(
    data: dict,
    masked_keys: Optional[set] = None,
    max_len: int = 500,
) -> str:
    """
    把消息体压成适合写日志的简述：屏蔽二进制大字段，超长时截断

    :param data: 待记录的消息体
    :param masked_keys: 屏蔽为占位符「<略>」的字段名集合，缺省为
        {"base64", "md5", "media_id", "thumb_media_id"}（base64 编码的图片、
        上传后的 media_id 等不宜整段落日志的大字段）
    :param max_len: 简述最大长度，超出部分截断并附「...<共 N 字符>」，缺省 500
    """
    if masked_keys is None:
        masked_keys = {"base64", "md5", "media_id", "thumb_media_id"}

    def walk(value):
        if isinstance(value, dict):
            return {
                k: "<略>" if k in masked_keys else walk(v) for k, v in value.items()
            }
        if isinstance(value, list):
            return [walk(item) for item in value]
        return value

    text = json.dumps(walk(data), ensure_ascii=False, default=str)
    if len(text) > max_len:
        return text[:max_len] + f"...<共 {len(text)} 字符>"
    return text
