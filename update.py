# -*- coding: UTF-8 -*-
import json
import os
import sys
import time
from urllib.parse import parse_qs, quote, urlparse

import requests as req
from fake_useragent import UserAgent

from SendMsg import SendMessage

path = os.path.join(sys.path[0], 'token.txt')

CLIENT_ID = os.getenv('CLIENT_ID', '').strip()
CLIENT_SECRET = os.getenv('CLIENT_SECRET', '').strip()
TOKEN_FIRST = os.getenv('TOKEN_FIRST', '').strip()
TENANT_ID = os.getenv('TENANT_ID', 'common').strip() or 'common'
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '15'))

REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:53682/').strip() or 'http://localhost:53682/'
AUTH_SCOPES = os.getenv(
    'AUTH_SCOPES',
    'offline_access openid profile User.Read',
).strip()

TOKEN_URL = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token'
AUTH_URL = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize'


class Update:
    @staticmethod
    def _send_msg(msg: str):
        try:
            SendMessage.send_tg_msg(msg)
        except Exception:
            pass

    @staticmethod
    def gettoken(refresh_token):
        if not CLIENT_ID or not CLIENT_SECRET:
            Update._send_msg(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + '\n' +
                'CLIENT_ID 或 CLIENT_SECRET 缺失，更新 token 失败'
            )
            return

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': UserAgent().random,
        }
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
        }

        html = req.post(TOKEN_URL, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
        html.raise_for_status()
        jsontxt = json.loads(html.text)
        new_refresh_token = jsontxt['refresh_token']

        with open(path, 'w+') as f:
            f.write(new_refresh_token)

    @staticmethod
    def update_token():
        try:
            if not os.path.exists(path):
                with open(path, 'w+') as f:
                    f.write('')

            with open(path, 'r+') as fo:
                refresh_token = fo.read().strip()

            if len(refresh_token) < 5:
                refresh_token = TOKEN_FIRST

            if len(refresh_token) < 5:
                Update._send_msg(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + '\n' +
                    'TOKEN_FIRST 为空，请先执行授权向导获取 refresh_token'
                )
                return

            Update.gettoken(refresh_token)
            Update._send_msg(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + '\n更新 token 成功')
        except Exception as e:
            Update._send_msg(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) +
                f'\n更新 token 失败: {repr(e)}'
            )

    @staticmethod
    def build_auth_url(state: str = 'graph_docker'):
        params = {
            'client_id': CLIENT_ID,
            'response_type': 'code',
            'redirect_uri': REDIRECT_URI,
            'response_mode': 'query',
            'scope': AUTH_SCOPES,
            'state': state,
            'prompt': 'select_account',
        }
        query = '&'.join(f'{k}={quote(v)}' for k, v in params.items())
        return f'{AUTH_URL}?{query}'

    @staticmethod
    def exchange_code_for_refresh_token(code: str):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': UserAgent().random,
        }
        data = {
            'client_id': CLIENT_ID,
            'scope': AUTH_SCOPES,
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code',
            'client_secret': CLIENT_SECRET,
        }

        resp = req.post(TOKEN_URL, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        js = json.loads(resp.text)
        if 'refresh_token' not in js:
            raise RuntimeError('授权成功但未返回 refresh_token，请检查 scopes 与应用类型')

        with open(path, 'w+') as f:
            f.write(js['refresh_token'])
        return js

    @staticmethod
    def parse_code_from_redirect_url(redirect_url: str):
        parsed = urlparse(redirect_url.strip())
        qs = parse_qs(parsed.query)
        if 'error' in qs:
            err = qs.get('error', ['unknown'])[0]
            desc = qs.get('error_description', [''])[0]
            raise RuntimeError(f'授权回调返回错误: {err} {desc}')
        code = qs.get('code', [None])[0]
        if not code:
            raise RuntimeError('回调 URL 中未找到 code 参数')
        return code


if __name__ == '__main__':
    Update.update_token()
