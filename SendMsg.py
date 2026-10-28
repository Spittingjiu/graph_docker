# -*- coding: UTF-8 -*-
import os
import requests as req

TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN', '').strip()
TG_SEND_ID = os.getenv('TG_SEND_ID', '').strip()
PROXY_URL = os.getenv('PROXY_URL', '').strip()
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '15'))


class SendMessage:
    @staticmethod
    def send_tg_msg(msg: str) -> bool:
        """
        发送 Telegram Bot 消息。
        优先使用 POST JSON，防止 GET 查询参数过长或特殊字符/换行符截断报错。
        """
        if not TG_BOT_TOKEN or not TG_SEND_ID:
            return False

        domain = "api.telegram.org"
        if PROXY_URL and PROXY_URL.lower() != "null":
            domain = PROXY_URL.replace("https://", "").replace("http://", "").strip("/")

        url = f"https://{domain}/bot{TG_BOT_TOKEN}/sendMessage"
        headers = {"Content-Type": "application/json"}

        # 尝试带 HTML 发送，若有未转义标签报 400 则自动回退纯文本发送
        for parse_mode in ("HTML", None):
            payload = {
                "chat_id": TG_SEND_ID,
                "text": msg,
                "disable_web_page_preview": True,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode

            try:
                resp = req.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    return True
                # 若 HTML 解析失败，循环继续尝试纯文本
                if resp.status_code == 400 and parse_mode == "HTML":
                    continue
                print(f"[TG] 发送失败 ({resp.status_code}): {resp.text[:200]}")
                return False
            except Exception as e:
                if parse_mode is None:
                    print(f"[TG] 网络请求异常: {repr(e)}")
        return False
