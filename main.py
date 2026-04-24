# -*- coding: UTF-8 -*-
import json
import os
import random
import sys
import time

import requests as req
from fake_useragent import UserAgent

from SendMsg import SendMessage
from update import Update

path = os.path.join(sys.path[0], 'token.txt')
num1 = 0

CLIENT_ID = os.getenv('CLIENT_ID', '').strip()
CLIENT_SECRET = os.getenv('CLIENT_SECRET', '').strip()
TENANT_ID = os.getenv('TENANT_ID', 'common').strip() or 'common'
IS_API_URLS_EXTEND = os.getenv('IS_API_URLS_EXTEND', 'false')
GRAPH_API_PROFILE = os.getenv('GRAPH_API_PROFILE', 'full').lower().strip()
GRAPH_APIS = os.getenv('GRAPH_APIS', '').strip()
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '15'))
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:53682/').strip() or 'http://localhost:53682/'

CYCLE_MIN = int(os.getenv('CYCLE_MIN', '3'))
CYCLE_MAX = int(os.getenv('CYCLE_MAX', '5'))
API_SLEEP_MIN = int(os.getenv('API_SLEEP_MIN', '3'))
API_SLEEP_MAX = int(os.getenv('API_SLEEP_MAX', '6'))
LOOP_SLEEP_MIN = int(os.getenv('LOOP_SLEEP_MIN', '20'))
LOOP_SLEEP_MAX = int(os.getenv('LOOP_SLEEP_MAX', '40'))

BASE_GRAPH_URL = 'https://graph.microsoft.com/v1.0'
TOKEN_URL = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token'


def send_msg(text: str):
    try:
        SendMessage.send_tg_msg(text)
    except Exception:
        pass


def _headers(access_token: str):
    return {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'User-Agent': UserAgent().random,
    }


def gettoken(refresh_token):
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

    resp = req.post(TOKEN_URL, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    jsontxt = json.loads(resp.text)
    return jsontxt['access_token']


def get_graph_api_urls():
    # 用户自定义优先
    if GRAPH_APIS:
        return [api.strip() for api in GRAPH_APIS.split(',') if api.strip()]

    # 轻量模式（默认）：只调用最小接口，降低权限申请复杂度
    if GRAPH_API_PROFILE in ('lite', 'minimal', 'mini'):
        return [
            '/me',  # User.Read
        ]

    # 全量模式：兼容历史行为
    return [
        '/me',
        '/me/messages',
        '/me/memberOf',
        '/groups',
        '/me/drive',
        '/me/drive/items/root',
        '/me/drive/root',
        '/me/drive/root/children',
        '/me/drive/sharedWithMe',
        '/drive/root',
        '/users',
        '/me/mailFolders/inbox/messageRules',
        '/me/mailFolders',
        '/me/outlook/masterCategories',
    ]


def use_api():
    global num1

    with open(path, 'r+') as fo:
        refresh_token = fo.read().strip()

    access_token = gettoken(refresh_token)
    headers = _headers(access_token)

    start_text = '此次运行开始时间为: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    print(start_text)
    send_msg(start_text)

    graph_api_urls = get_graph_api_urls()

    # 可选补充 API（按需授权）
    graph_api_urls_extend = [
        BASE_GRAPH_URL + '/me/calendars',  # Calendars.Read
        BASE_GRAPH_URL + '/me/contacts',  # Contacts.Read
    ]
    other_api_urls_extend = []

    for url in graph_api_urls:
        full_url = BASE_GRAPH_URL + url
        try:
            status_code = req.get(full_url, headers=headers, timeout=REQUEST_TIMEOUT).status_code
            if status_code == 200:
                num1 += 1
                text = '调用成功: ' + str(num1) + ' 次'
                print(text + ' -> ' + full_url)
                send_msg(text)
            else:
                text = f"！！！状态码不是 200({status_code})，api: {full_url} ！！！"
                print(text)
                send_msg(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + '\n' + text)

            time.sleep(random.randint(API_SLEEP_MIN, API_SLEEP_MAX))
        except Exception as e:
            text = f'！！！调用失败，api: {full_url} ！！！'
            print(text)
            print(repr(e))
            send_msg(text)
            time.sleep(random.randint(API_SLEEP_MIN, API_SLEEP_MAX))

    if IS_API_URLS_EXTEND.lower() == 'true':
        print('调用补充 API 地址 开始')
        send_msg('调用补充 API 地址 开始')
        for url in graph_api_urls_extend + other_api_urls_extend:
            try:
                status_code = req.get(url, headers=headers, timeout=REQUEST_TIMEOUT).status_code
                if status_code == 200:
                    num1 += 1
                    text = '调用成功: ' + str(num1) + ' 次'
                    print(text + ' -> ' + url)
                    send_msg(text)
                else:
                    text = f"！！！状态码不是 200({status_code})，api: {url} ！！！"
                    print(text)
                    send_msg(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + '\n' + text)
                time.sleep(random.randint(API_SLEEP_MIN, API_SLEEP_MAX))
            except Exception as e:
                text = f'！！！调用失败，api: {url} ！！！'
                print(text)
                print(repr(e))
                send_msg(text)
                time.sleep(random.randint(API_SLEEP_MIN, API_SLEEP_MAX))

        print('调用补充 API 地址 结束')
        send_msg('调用补充 API 地址 结束')


def format_time(time_diff):
    if time_diff < 60:
        return '耗时%.0f秒' % time_diff
    elif time_diff < 3600:
        minutes, seconds = divmod(time_diff, 60)
        return '耗时%d分%.0f秒' % (minutes, seconds)
    else:
        hours, seconds = divmod(time_diff, 3600)
        minutes, seconds = divmod(seconds, 60)
        return '耗时%d小时%d分%.0f秒' % (hours, minutes, seconds)


if __name__ == '__main__':
    start_time = time.time()
    start_text = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' Microsoft API 应用 开始'
    print(start_text)
    send_msg(start_text)

    try:
        Update.update_token()

        if CYCLE_MIN > CYCLE_MAX:
            CYCLE_MIN, CYCLE_MAX = CYCLE_MAX, CYCLE_MIN
        cycle_count = random.randint(CYCLE_MIN, CYCLE_MAX)

        for i in range(cycle_count):
            loop_text = '第' + str(i + 1) + '次循环'
            print(loop_text)
            send_msg(loop_text)
            use_api()
            if i < cycle_count - 1:
                time.sleep(random.randint(LOOP_SLEEP_MIN, LOOP_SLEEP_MAX))

        end_text = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' Microsoft API 应用 结束'
        print(end_text)
        send_msg(end_text)

    except Exception as e:
        err_text = '主流程异常退出: ' + repr(e)
        print(err_text)
        send_msg(err_text)

    time_diff = time.time() - start_time
    format_time_str = format_time(time_diff)
    print(format_time_str)
    send_msg(format_time_str)
