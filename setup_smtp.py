"""Interactively store SMTP credentials locally. Never prints the authorization code."""
import getpass
import json
import os
from pathlib import Path
from email.utils import parseaddr


def email_address(value):
    if any(c in value for c in '\r\n') or parseaddr(value)[1] != value or '@' not in value:
        raise ValueError('请输入完整的邮箱地址')
    return value


def main():
    path = Path(__file__).resolve().parent / 'smtp.local.json'
    if path.exists() and input('本地配置已存在，覆盖？[y/N]：').strip().lower() != 'y':
        print('保留现有配置。')
        return
    username = email_address(input('SMTP 登录邮箱：').strip())
    recipient = email_address(input('收件邮箱 [默认同登录邮箱]：').strip() or username)
    host = input('SMTP SSL 服务器 [smtp.qq.com]：').strip() or 'smtp.qq.com'
    port = int(input('SMTP SSL 端口 [465]：').strip() or '465')
    if not 1 <= port <= 65535:
        raise ValueError('端口必须在 1 至 65535 之间')
    password = getpass.getpass('SMTP 授权码（输入不可见，不是邮箱密码）：').strip()
    if not password:
        raise ValueError('授权码不能为空')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(dict(host=host, port=port, username=username,
                       recipient=recipient, password=password), stream)
    print('本地配置已保存。请先预览，再发送测试邮件。')


if __name__ == '__main__':
    main()
