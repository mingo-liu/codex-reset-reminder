import argparse
import fcntl
import hashlib
import json
import math
import os
import smtplib
import ssl
from html import escape
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo('Asia/Shanghai')

def cards_from(payload, now):
    if 'rateLimitResetCredits' not in payload:
        raise ValueError('查询结果缺少重置卡字段，不能按零张处理')
    result = []
    for card in payload['rateLimitResetCredits']['credits']:
        if card['status'] == 'available' and card['expiresAt'] > now:
            result.append(card)
    return sorted(result, key=lambda c: c['expiresAt'])

def due(cards, now, state):
    local = datetime.fromtimestamp(now, TZ)
    jobs = []
    key = 'daily:' + local.date().isoformat()
    if local.weekday() in (0, 3) and local.hour == 9 and key not in state:
        jobs.append((key, 'daily', cards))
    for c in cards:
        key = f"expiry:{c['id']}:{c['expiresAt']}"
        if 0 < c['expiresAt'] - now <= 7200 and key not in state:
            jobs.append((key, 'expiry', [c]))
    return jobs

def render(kind, cards, now, recipient=''):
    alert = kind == 'expiry'
    color = '#b67529' if alert else '#133d32'
    if alert:
        mins = max(1, math.ceil((cards[0]['expiresAt'] - now)/60))
        title = f'这张重置卡，还有 {mins} 分钟就到期了。'
        subject = f'Codex 重置卡即将到期 · 剩余 {mins} 分钟'
    else:
        title = '别让你的重置卡过期。' if cards else '今天暂无可用重置卡。'
        subject = f'Codex 重置卡简报 · {len(cards)} 张重置卡可用'
    rows = ''
    plain = [subject, '']
    for i, card in enumerate(cards):
        d = datetime.fromtimestamp(card['expiresAt'], TZ)
        remaining = max(1, math.ceil((card['expiresAt']-now)/60))
        days, rem = divmod(remaining, 1440)
        hours, minutes = divmod(rem, 60)
        left = (f'{days} 天 ' if days else '') + f'{hours} 小时 {minutes} 分钟'
        scope = '每周额度 + 5 小时额度' if card.get('resetType') == 'codexRateLimits' else escape(card.get('title','额度重置'))
        badge = '即将到期' if alert else ('最早到期' if i == 0 else '可用')
        rows += f'''<tr><td style="padding:0 28px 14px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #dfe6dd;border-radius:16px;background:{'#fffbf5' if alert else '#f7faf5'}"><tr><td style="padding:22px"><table role="presentation" width="100%"><tr><td style="font-size:16px;font-weight:600">↻ &nbsp;完整额度重置</td><td align="right"><span style="font-size:11px;border-radius:18px;padding:6px 10px;background:#e8eedb;color:#657346">{badge}</span></td></tr></table><p style="font-size:12px;color:#738375;margin:12px 0 22px">{scope}</p><div style="border-top:1px dashed #d5dfce;padding-top:16px;font-size:12px;color:#72816e">到期时间 · 北京时间</div><div style="font-size:24px;font-weight:600;margin-top:6px">{d.month} 月 {d.day} 日 &nbsp;{d:%H:%M}</div><div style="font-size:11px;color:#81907b;margin-top:8px">{d.year} 年 · 精确截止 {d:%H:%M:%S}</div><div style="font-size:12px;color:#71816b;margin-top:12px">剩余 {left}</div></td></tr></table></td></tr>'''
        plain.append(f'{scope}\n到期：{d:%Y-%m-%d %H:%M:%S}（北京时间）\n剩余：{left}\n')
    summary = '' if alert else f'<div style="margin-top:26px;border-top:1px solid #386052;padding-top:20px"><span style="font-size:46px;color:#d7f6a5;font-weight:650">{len(cards):02d}</span><span style="font-size:12px;color:#c1d8cd"> &nbsp;张可用</span></div>'
    html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0;background:#edf1f0;color:#17352e;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 12px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:white;border:1px solid #dce6e1;border-radius:24px;overflow:hidden"><tr><td style="padding:32px;background:{color};color:white"><div style="font-size:12px;letter-spacing:2px">↻ &nbsp; CODEX / {'到期提醒' if alert else '重置卡简报'}</div><h1 style="font-size:29px;line-height:1.5;font-weight:600;margin:28px 0 0">{title}</h1>{summary}</td></tr><tr><td style="padding:24px 28px 18px;font-size:12px;color:#72877d;letter-spacing:2px">{'即将到期的重置卡' if alert else '你的可用重置卡'}</td></tr>{rows}<tr><td style="padding:20px 28px;background:#f8faf9;font-size:11px;color:#8b9991;line-height:1.9">{escape(recipient)}<br>{datetime.fromtimestamp(now,TZ):%Y-%m-%d %H:%M} · 北京时间 UTC+8</td></tr></table></td></tr></table></body></html>'''
    return subject, '\n'.join(plain), html

def send(config, key, subject, plain, html):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f"Codex 额度提醒 <{config['username']}>"
    msg['To'] = config.get('recipient', config['username'])
    msg['Date'] = format_datetime(datetime.now(TZ))
    msg['Message-ID'] = '<' + hashlib.sha256(key.encode()).hexdigest() + '@codex-reset.local>'
    msg.set_content(plain)
    msg.add_alternative(html, subtype='html')
    with smtplib.SMTP_SSL(config['host'], config['port'], context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(config['username'], config['password'])
        smtp.send_message(msg)

def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preview', action='store_true')
    mode.add_argument('--test', action='store_true')
    args = parser.parse_args()
    now = datetime.now(TZ).timestamp()
    payload = json.loads(Path(args.input).read_text())
    cards = cards_from(payload, now)
    if args.preview:
        for kind in ['daily', 'expiry'] if cards else ['daily']:
            selected = cards if kind == 'daily' else cards[:1]
            (ROOT / f'{kind}.html').write_text(render(kind, selected, now)[2])
        print('预览已生成；未发送邮件。')
        return
    config_path = ROOT/'smtp.local.json'
    if not config_path.exists():
        raise ValueError('SMTP_NOT_CONFIGURED')
    config = json.loads(config_path.read_text())
    with (ROOT/'state.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path = ROOT/'state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        jobs = [('test:'+str(now), 'daily', cards)] if args.test else due(cards, now, state)
        for key, kind, selected in jobs:
            subject, plain, html = render(kind, selected, now, config.get('recipient', config['username']))
            send(config, key, ('[测试] ' if args.test else '')+subject, plain, html)
            state[key] = now
            temp = ROOT/'state.tmp'
            temp.write_text(json.dumps(state))
            os.replace(temp, state_path)
        print(f'SENT={len(jobs)}')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # SMTP responses may contain sensitive account information; do not print them.
        print('SEND_FAILED: '+type(exc).__name__)
        raise SystemExit(1)
