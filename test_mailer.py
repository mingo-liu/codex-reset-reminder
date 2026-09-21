import unittest
from datetime import datetime
from mailer import TZ, cards_from, due, render, send
from unittest.mock import patch
class Scheduling(unittest.TestCase):
    def test_due_boundaries_and_dedup(self):
        now = datetime(2026,10,5,9,0,tzinfo=TZ).timestamp()
        card = dict(id='a', status='available', expiresAt=now+7200,resetType='codexRateLimits')
        jobs = due([card], now, {})
        self.assertEqual([j[1] for j in jobs], ['daily','expiry'])
        self.assertEqual(due([card],now,{j[0]:now for j in jobs}), [])
        self.assertEqual(due([card],now-1,{}), [])
        self.assertEqual([j[1] for j in due([card],now+7200,{jobs[0][0]:now})], [])
    def test_summary_weekdays(self):
        for day in range(5, 12):
            now = datetime(2026, 10, day, 9, 0, tzinfo=TZ).timestamp()
            self.assertEqual(bool(due([], now, {})), day in (5, 8))
        now = datetime(2026, 10, 6, 9, 0, tzinfo=TZ).timestamp()
        card = dict(id='a', status='available', expiresAt=now+7200)
        self.assertEqual([j[1] for j in due([card], now, {})], ['expiry'])

    def test_no_evening_catchup(self):
        for hour in (8, 10, 18, 23):
            now = datetime(2026, 9, 21, hour, 1, tzinfo=TZ).timestamp()
            self.assertEqual(due([], now, {}), [])
        now = datetime(2026, 9, 21, 9, 1, tzinfo=TZ).timestamp()
        self.assertEqual([j[1] for j in due([], now, {})], ['daily'])

    def test_consumed_and_expired(self):
        cards=[dict(id='a',status='used',expiresAt=200),dict(id='b',status='available',expiresAt=99)]
        self.assertEqual(cards_from({'rateLimitResetCredits':{'credits':cards}},100),[])
        with self.assertRaises(ValueError): cards_from({},100)
    def test_mail_content(self):
        c=dict(id='a',status='available',expiresAt=3700,resetType='codexRateLimits')
        subject,plain,html=render('expiry',[c],100)
        self.assertIn('60 分钟',subject)
        self.assertIn('每周额度 + 5 小时额度',html)
        self.assertNotIn('查看使用条件',html)
        self.assertIn('0 张',render('daily',[],100)[0])
class PrivacyAndDelivery(unittest.TestCase):
    def test_configured_recipient_and_legacy_default(self):
        config = dict(host='smtp.example.com', port=465, username='sender@example.com',
                      password='fake-test-token', recipient='recipient@example.com')
        with patch('mailer.smtplib.SMTP_SSL') as smtp:
            send(config, 'test-key', '测试', '文本', '<p>测试</p>')
            msg = smtp.return_value.__enter__.return_value.send_message.call_args[0][0]
            self.assertEqual(msg['To'], 'recipient@example.com')
            self.assertEqual(msg.get_content_type(), 'multipart/alternative')
            del config['recipient']
            send(config, 'test-key', '测试', '文本', '<p>测试</p>')
            msg = smtp.return_value.__enter__.return_value.send_message.call_args[0][0]
            self.assertEqual(msg['To'], 'sender@example.com')

    def test_html_escapes_config_and_card_data(self):
        card = dict(id='demo', expiresAt=3700, title='<script>unsafe</script>')
        html = render('daily', [card], 100, '<private@example.com>')[2]
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;private@example.com&gt;', html)

if __name__=='__main__': unittest.main()
