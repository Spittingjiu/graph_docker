#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from update import Update


def main():
    print('=== graph_docker 首次授权向导（替代 rclone）===')
    print('1) 打开下面的授权链接，登录并同意权限')
    auth_url = Update.build_auth_url()
    print('\n' + auth_url + '\n')

    print('2) 浏览器会跳转到你的 redirect_uri（可能打不开是正常的）')
    print('3) 把完整回跳 URL 粘贴到这里，按回车')
    redirect_url = input('\n回跳 URL: ').strip()

    try:
        code = Update.parse_code_from_redirect_url(redirect_url)
        Update.exchange_code_for_refresh_token(code)
        print('\n✅ 授权完成：refresh_token 已写入 token.txt')
    except Exception as e:
        print(f'\n❌ 授权失败: {repr(e)}')
        raise


if __name__ == '__main__':
    main()
