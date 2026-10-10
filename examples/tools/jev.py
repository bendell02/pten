"""调用 TypeSafe AI 的 jev 模型（System One API）做结构化决策。

输入 state（一段文本或 JSON 结构）和一组问题，jev 返回类型化答案：
Noul（是非，返回 0~1 概率）/ Choice（单选）/ Score（按等级打分），
一次调用可同时问多个问题。

运行前提：api_key 三选一——构造参数 api_key、配置文件 [jev] 段、
或环境变量 TYPESAFE_API_KEY；base_url / model / proxy 均可省略
（省略时 base_url/model 用 SDK 默认值；需代理时在 [jev] 或 [proxies] 段配置）。
运行方式：python examples/tools/jev.py
"""

from pten.tools.jev import Choice, Jev, Noul, Score

if __name__ == "__main__":
    # state：待判断内容（此处为一条客服工单，也可以是 dict 等结构）
    ticket = "Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP."

    # questions：一组结构化问题，键为自定义问题名
    questions = {
        "is_urgent": Noul(
            instructions="The message conveys urgency or time-sensitivity",
        ),
        "department": Choice(
            instructions="Which team should handle this",
            criteria={
                "billing": "Payment or subscription issues",
                "technical": "Bugs or integration problems",
                "sales": "Pricing or account questions",
            },
        ),
        "frustration": Score(
            instructions="How frustrated the customer appears",
            criteria=[
                "Calm, just stating facts",
                "Frustrated but civil",
                "Very angry, strong language",
            ],
        ),
    }

    # 配置缺省时从 pten_keys.ini 的 [jev] 段读取；无法直连 typesafe.ai 的
    # 区域在 [jev] 段配 proxy（或复用全局 [proxies] 段）
    with Jev() as jev:
        response = jev.ask(ticket, questions)

        # 答案按问题名取，类型分别为 float(0~1 概率) / str / float
        print("is_urgent:", response.answers["is_urgent"].noul)
        print("department:", response.answers["department"].choice)
        print("frustration:", response.answers["frustration"].score)
