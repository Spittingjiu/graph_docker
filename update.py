# -*- coding: UTF-8 -*-
import json
import os
import sys
import time
from urllib.parse import parse_qs, quote, urlparse

import requests as req
from fake_useragent import UserAgent

from SendMsg import SendMessage

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
    def get_token_path() -> str:
        """
        获取 token.txt 存储路径，优先持久化到 data 目录，兼容根目录。
        """
        base_dir = sys.path[0]
        data_dir = os.path.join(base_dir, 'data')
        data_token = os.path.join(data_dir, 'token.txt')
        root_token = os.path.join(base_dir, 'token.txt')

        # 若 data 目录存在或已有 data/token.txt 则优先使用
        if os.path.isdir(data_dir) or os.path.exists(data_token):
            return data_token
        return root_token

    @staticmethod
    def save_token(token_str: str) -> None:
        """
        安全写入 token 并落盘同步。
        """
        target_path = Update.get_token_path()
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(token_str.strip())
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass

        # 若同时存在根目录 token.txt 且与 target_path 不同，同步写入保证兼容
        root_token = os.path.join(sys.path[0], 'token.txt')
        if os.path.abspath(target_path) != os.path.abspath(root_token) and os.path.exists(root_token):
            try:
                with open(root_token, 'w', encoding='utf-8') as f:
                    f.write(token_str.strip())
                    f.flush()
            except OSError:
                pass

    @staticmethod
    def _send_msg(msg: str):
        try:
            SendMessage.send_tg_msg(msg)
        except Exception:
            pass

    @staticmethod
    def gettoken(refresh_token: str):
        """
        向微软换取新的 token，返回包含 access_token 和 refresh_token 的字典。
        """
        if not CLIENT_ID or not CLIENT_SECRET:
            raise RuntimeError('CLIENT_ID 或 CLIENT_SECRET 缺失，无法更新 token')

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': UserAgent().random,
        }
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token.strip(),
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
        }

        resp = req.post(TOKEN_URL, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            err_msg = resp.text
            try:
                err_json = resp.json()
                err_msg = err_json.get('error_description') or err_json.get('error') or err_msg
            except Exception:
                pass
            raise RuntimeError(f"微软 Token 刷新失败 (HTTP {resp.status_code}): {err_msg}")

        jsontxt = resp.json()
        new_refresh_token = jsontxt.get('refresh_token')
        access_token = jsontxt.get('access_token')
        expires_in = int(jsontxt.get('expires_in', 3600))

        if not new_refresh_token:
            raise RuntimeError('刷新 token 响应中缺少 refresh_token')

        Update.save_token(new_refresh_token)

        return {
            'access_token': access_token,
            'refresh_token': new_refresh_token,
            'expires_in': expires_in
        }

    @staticmethod
    def update_token():
        try:
            token_path = Update.get_token_path()
            refresh_token = ''
            if os.path.exists(token_path):
                with open(token_path, 'r', encoding='utf-8') as fo:
                    refresh_token = fo.read().strip()

            if len(refresh_token) < 5:
                refresh_token = TOKEN_FIRST

            if len(refresh_token) < 5:
                Update._send_msg(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + '\n' +
                    '⚠️ TOKEN_FIRST 为空，请先执行 ./graphctl auth 完成授权向导'
                )
                return False

            res = Update.gettoken(refresh_token)
            return bool(res)
        except Exception as e:
            err_str = repr(e)
            print(f"[Update] 更新 Token 失败: {err_str}")
            Update._send_msg(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) +
                f'\n❌ 更新 token 失败: {err_str}'
            )
            return False

    @staticmethod
    def build_auth_url(state: str = 'graph_docker'):
        if not CLIENT_ID:
            raise RuntimeError('CLIENT_ID 为空，请先完成 tenant-init 或检查 .env')
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
        if not CLIENT_ID or not CLIENT_SECRET:
            raise RuntimeError('CLIENT_ID/CLIENT_SECRET 为空，请先完成 tenant-init 或检查 .env')
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': UserAgent().random,
        }
        data = {
            'client_id': CLIENT_ID,
            'scope': AUTH_SCOPES,
            'code': code.strip(),
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code',
            'client_secret': CLIENT_SECRET,
        }

        resp = req.post(TOKEN_URL, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            err_msg = resp.text
            try:
                err_json = resp.json()
                err_msg = err_json.get('error_description') or err_json.get('error') or err_msg
            except Exception:
                pass
            raise RuntimeError(f"换取 Token 失败 (HTTP {resp.status_code}): {err_msg}")

        js = resp.json()
        if 'refresh_token' not in js:
            raise RuntimeError('授权成功但未返回 refresh_token，请检查 scopes 与应用类型')

        Update.save_token(js['refresh_token'])
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
