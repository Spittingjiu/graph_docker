# -*- coding: UTF-8 -*-
import json
import os
import random
import signal
import sys
import time

import requests as req
from fake_useragent import UserAgent

from SendMsg import SendMessage
from update import Update

CLIENT_ID = os.getenv('CLIENT_ID', '').strip()
CLIENT_SECRET = os.getenv('CLIENT_SECRET', '').strip()
TENANT_ID = os.getenv('TENANT_ID', 'common').strip() or 'common'
IS_API_URLS_EXTEND = os.getenv('IS_API_URLS_EXTEND', 'false')
GRAPH_API_PROFILE = os.getenv('GRAPH_API_PROFILE', 'full').lower().strip()
GRAPH_APIS = os.getenv('GRAPH_APIS', '').strip()
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '15'))
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:53682/').strip() or 'http://localhost:53682/'

# 运行模式: loop(常驻定时循环，默认) / once(执行单次批处理后退出)
RUN_MODE = os.getenv('RUN_MODE', 'loop').lower().strip()
RUN_INTERVAL_HOURS = float(os.getenv('RUN_INTERVAL_HOURS', '6'))
JITTER_MINUTES = float(os.getenv('JITTER_MINUTES', '30'))

# Telegram 通知模式: summary(单次批处理汇总，默认) / all(每次API调用都发) / error(仅出错时发送)
TG_NOTIFY_MODE = os.getenv('TG_NOTIFY_MODE', 'summary').lower().strip()

CYCLE_MIN = int(os.getenv('CYCLE_MIN', '3'))
CYCLE_MAX = int(os.getenv('CYCLE_MAX', '5'))
API_SLEEP_MIN = int(os.getenv('API_SLEEP_MIN', '3'))
API_SLEEP_MAX = int(os.getenv('API_SLEEP_MAX', '6'))
LOOP_SLEEP_MIN = int(os.getenv('LOOP_SLEEP_MIN', '20'))
LOOP_SLEEP_MAX = int(os.getenv('LOOP_SLEEP_MAX', '40'))

BASE_GRAPH_URL = 'https://graph.microsoft.com/v1.0'

# 内存缓存 access_token
_TOKEN_CACHE = {
    'access_token': None,
    'expires_at': 0,
}

_RUNNING = True


def _signal_handler(signum, frame):
    global _RUNNING
    print(f"\n[SYSTEM] 接收到退出信号 ({signum})，正在安全停止...")
    _RUNNING = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


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


def get_cached_access_token() -> str:
    """
    智能内存 Token 缓存：
    有效期内直接复用 access_token，避免每次 API 调用都发起冗余 OAuth 请求。
    """
    now = time.time()
    if _TOKEN_CACHE['access_token'] and _TOKEN_CACHE['expires_at'] > (now + 300):
        return _TOKEN_CACHE['access_token']

    token_path = Update.get_token_path()
    refresh_token = ''
    if os.path.exists(token_path):
        with open(token_path, 'r', encoding='utf-8') as fo:
            refresh_token = fo.read().strip()

    if len(refresh_token) < 5:
        refresh_token = os.getenv('TOKEN_FIRST', '').strip()

    if len(refresh_token) < 5:
        raise RuntimeError('未找到有效的 refresh_token，请先执行 ./graphctl auth 完成授权')

    token_data = Update.gettoken(refresh_token)
    if isinstance(token_data, dict) and 'access_token' in token_data:
        _TOKEN_CACHE['access_token'] = token_data['access_token']
        _TOKEN_CACHE['expires_at'] = now + int(token_data.get('expires_in', 3600))
        return _TOKEN_CACHE['access_token']

    raise RuntimeError('向微软换取 access_token 失败')


def get_graph_api_urls():
    if GRAPH_APIS:
        return [api.strip() for api in GRAPH_APIS.split(',') if api.strip()]

    if GRAPH_API_PROFILE in ('lite', 'minimal', 'mini'):
        return ['/me']

    # 默认全量模式
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


def run_single_batch():
    """
    运行单批次 API 调用循环
    """
    batch_start = time.time()
    now_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    print(f"[{now_str}] === 开始执行批次巡检 ===")

    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'failed_apis': [],
    }

    c_min = CYCLE_MIN
    c_max = CYCLE_MAX
    if c_min > c_max:
        c_min, c_max = c_max, c_min
    cycle_count = random.randint(c_min, c_max)

    graph_api_urls_extend = [
        BASE_GRAPH_URL + '/me/calendars',
        BASE_GRAPH_URL + '/me/contacts',
    ]

    for cycle_idx in range(cycle_count):
        if not _RUNNING:
            break

        print(f"\n--- 第 {cycle_idx + 1}/{cycle_count} 轮循环 ---")
        access_token = get_cached_access_token()
        headers = _headers(access_token)

        # 获取 API 列表并乱序，模拟真实访问行为
        apis = list(get_graph_api_urls())
        random.shuffle(apis)

        for api_path in apis:
            if not _RUNNING:
                break

            full_url = BASE_GRAPH_URL + api_path
            stats['total'] += 1
            try:
                resp = req.get(full_url, headers=headers, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    stats['success'] += 1
                    msg = f"调用成功: {stats['success']} 次 -> {full_url}"
                    print(msg)
                    if TG_NOTIFY_MODE == 'all':
                        send_msg(msg)
                elif resp.status_code == 429:
                    stats['failed'] += 1
                    stats['failed_apis'].append(api_path)
                    retry_after = resp.headers.get('Retry-After', '30')
                    wait_sec = int(retry_after) if retry_after.isdigit() else 30
                    print(f"⚠️ 微软 API 速率限制 (HTTP 429)，等待 {wait_sec} 秒...")
                    time.sleep(wait_sec)
                else:
                    stats['failed'] += 1
                    stats['failed_apis'].append(f"{api_path}({resp.status_code})")
                    err_msg = f"状态码异常 ({resp.status_code}): {full_url}"
                    print(err_msg)
                    if TG_NOTIFY_MODE == 'all':
                        send_msg(err_msg)

                time.sleep(random.randint(API_SLEEP_MIN, API_SLEEP_MAX))
            except Exception as e:
                stats['failed'] += 1
                stats['failed_apis'].append(f"{api_path}(err)")
                err_msg = f"调用接口失败: {full_url} ({repr(e)})"
                print(err_msg)
                if TG_NOTIFY_MODE == 'all':
                    send_msg(err_msg)
                time.sleep(random.randint(API_SLEEP_MIN, API_SLEEP_MAX))

        # 扩展接口
        if IS_API_URLS_EXTEND.lower() == 'true':
            for ext_url in graph_api_urls_extend:
                if not _RUNNING:
                    break
                stats['total'] += 1
                try:
                    resp = req.get(ext_url, headers=headers, timeout=REQUEST_TIMEOUT)
                    if resp.status_code == 200:
                        stats['success'] += 1
                        msg = f"扩展接口成功: {stats['success']} 次 -> {ext_url}"
                        print(msg)
                        if TG_NOTIFY_MODE == 'all':
                            send_msg(msg)
                    else:
                        stats['failed'] += 1
                        stats['failed_apis'].append(f"{ext_url}({resp.status_code})")
                        print(f"扩展接口状态码异常 ({resp.status_code}): {ext_url}")
                    time.sleep(random.randint(API_SLEEP_MIN, API_SLEEP_MAX))
                except Exception as e:
                    stats['failed'] += 1
                    stats['failed_apis'].append(f"{ext_url}(err)")
                    print(f"扩展接口失败: {ext_url} ({repr(e)})")
                    time.sleep(random.randint(API_SLEEP_MIN, API_SLEEP_MAX))

        if cycle_idx < cycle_count - 1 and _RUNNING:
            sleep_wait = random.randint(LOOP_SLEEP_MIN, LOOP_SLEEP_MAX)
            print(f"轮次间隔休眠 {sleep_wait} 秒...")
            time.sleep(sleep_wait)

    duration_str = format_time(time.time() - batch_start)
    end_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    print(f"\n[{end_str}] === 批次巡检完成 ===")
    print(f"完成轮数: {cycle_count} 轮 | 成功: {stats['success']} 次 | 失败: {stats['failed']} 次 | 耗时: {duration_str}")

    return stats, cycle_count, duration_str


def format_time(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}分{s}秒"
    else:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}小时{m}分{s}秒"


def main():
    print(r"""
======================================================
  Graph Docker - Microsoft Graph API 保活服务
======================================================
""")
    print(f"运行模式: {RUN_MODE.upper()}")
    if RUN_MODE == 'loop':
        print(f"定时间隔: 每 {RUN_INTERVAL_HOURS} 小时 (浮动 ±{JITTER_MINUTES}分钟)")
    print(f"通知级别: {TG_NOTIFY_MODE.upper()}")
    print(f"接口配置: PROFILE={GRAPH_API_PROFILE.upper()}")
    print("------------------------------------------------------")

    while _RUNNING:
        try:
            stats, cycles, duration_str = run_single_batch()

            # 汇总消息通知
            summary_msg = (
                f"<b>🟢 Microsoft Graph 巡检完成</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📅 <b>时间</b>: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n"
                f"🔁 <b>轮数</b>: {cycles} 轮\n"
                f"✅ <b>成功</b>: {stats['success']} 次\n"
                f"❌ <b>失败</b>: {stats['failed']} 次\n"
                f"⏳ <b>耗时</b>: {duration_str}"
            )
            if stats['failed'] > 0:
                uniq_errs = list(dict.fromkeys(stats['failed_apis']))[:5]
                summary_msg += f"\n⚠️ <b>异常接口</b>: <code>{', '.join(uniq_errs)}</code>"

            if RUN_MODE != 'loop':
                if TG_NOTIFY_MODE in ('summary', 'all') or (TG_NOTIFY_MODE == 'error' and stats['failed'] > 0):
                    send_msg(summary_msg)
                break

            # 常驻定时模式下计算下一次延迟
            base_sec = RUN_INTERVAL_HOURS * 3600.0
            jitter_sec = random.uniform(-JITTER_MINUTES * 60.0, JITTER_MINUTES * 60.0)
            sleep_duration = max(300, int(base_sec + jitter_sec))
            next_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + sleep_duration))

            summary_msg += f"\n💤 <b>下次执行</b>: {next_time_str}"
            if TG_NOTIFY_MODE in ('summary', 'all') or (TG_NOTIFY_MODE == 'error' and stats['failed'] > 0):
                send_msg(summary_msg)

            print(f"\n[SCHEDULER] 本轮完成，进入休眠 {format_time(sleep_duration)}，下次执行时间: {next_time_str}")

            # 分段 sleep 支持优雅退出
            slept = 0
            while slept < sleep_duration and _RUNNING:
                step = min(5, sleep_duration - slept)
                time.sleep(step)
                slept += step

        except Exception as e:
            err_text = f"❌ [Graph Docker] 运行异常: {repr(e)}"
            print(f"\n{err_text}")
            send_msg(err_text)

            if RUN_MODE != 'loop':
                sys.exit(1)

            print("[SCHEDULER] 发生异常，等待 10 分钟后重试...")
            time.sleep(600)

    print("\n[SYSTEM] 程序已正常退出。")


if __name__ == '__main__':
    main()
