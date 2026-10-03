from pten.utils import brief_for_log


def test_brief_for_log_keeps_text_content():
    brief = brief_for_log({"msg_type": "text", "content": {"text": "你好，world"}})
    # ensure_ascii=False，中文原样输出而不是 \uXXXX 转义
    assert "你好，world" in brief


def test_brief_for_log_masks_binary_fields():
    data = {
        "msgtype": "image",
        "image": {"base64": "aGVsbG8=", "md5": "d41d8cd98f00b204e9800998ecf8427e"},
    }
    brief = brief_for_log(data)
    assert '"base64": "<略>"' in brief
    assert '"md5": "<略>"' in brief
    assert "aGVsbG8=" not in brief


def test_brief_for_log_masks_fields_nested_in_list():
    # 列表元素里的字段同样要走到（如 news.articles[].thumb_media_id）
    data = {"news": {"articles": [{"title": "t", "thumb_media_id": "abc"}]}}
    brief = brief_for_log(data)
    assert '"thumb_media_id": "<略>"' in brief
    assert "abc" not in brief


def test_brief_for_log_truncates_long_content():
    data = {"text": {"content": "长" * 600}}
    brief = brief_for_log(data)
    assert "...<共 " in brief
    assert "长" * 600 not in brief


def test_brief_for_log_custom_masked_keys_and_max_len():
    # masked_keys / max_len 可按调用覆盖：屏蔽指定字段、放宽或收紧长度
    data = {"token": "secret_value", "content": {"text": "你好"}}
    brief = brief_for_log(data, masked_keys={"token"}, max_len=20)
    assert '"token": "<略>"' in brief
    assert "secret_value" not in brief
    assert "...<共 " in brief
