import base64
import hashlib
import hmac
import json
import re
import threading
import time
from urllib.parse import urlencode

import execjs
from PIL import Image

import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('TkAgg')

import scrapy

class UserSpider(scrapy.Spider):
    name = 'user'
    allowed_domains = ['zhihu.com']
    start_urls = ['https://www.zhihu.com/']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2,
        'LOG_LEVEL': 'ERROR',
    }

    headers = {
        'Host': 'www.zhihu.com',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'
    }

    def parse(self, response):
        pass

    def start_requests(self):
        login_url = 'https://www.zhihu.com/signup?next=%2F'

        yield scrapy.Request(
            login_url,
            headers=self.headers,
            dont_filter=True,
            callback=self.login,
        )

    def login(self, response):
        # 需要提交的头信息，可以通过抓包工具或浏览器控制台得到相关信息
        headers_info = {
            # 通用头
            'com_headers': {
                'hHost': 'www.zhihu.com',
                'accept-encoding': 'gzip, deflate, br',
                'referer': 'https://www.zhihu.com/',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36',
            },
            # 请求头
            'req_headers': {},
            # 响应头
            'res_headers': {
                'content-type': 'application/x-www-form-urlencoded',
                # 访问首页时从 `Response Headers` 的 `Set-Cookie` 字段中可以找到
                'x-xsrftoken': '',
                'x-zse-83': '3_1.1',
            },
        }
        # 登录时，可以在浏览器控制台通过打断点的方式，得到需要提交的表单字段信息
        form_info = {
            # 客户端 ID：一定时间内该值不会发生变化
            'client_id': 'c3cef7c66a1843f8b3a9e6a1e3160e20',
            # 授权类型
            'grant_type': 'password',
            'source': 'com.zhihu.web',
            # 账户名：如果是手机号，需要在手机号前面加上国际区号（+86 表示中国大陆），如 '+8613888888888'
            'username': '+86123',
            # 账号密码
            'password': '123',
            # 语言: en / cn
            'lang': 'en',
            'ref_source': 'homepage',
            'utm_source': '',
            # 验证码: 会根据不同的语言得到不同形式的验证码（en - 填写4位验证码， cn - 点击倒立的汉字）
            'captcha': '',
            # 时间戳：13 位，需要我们自行构建（time.time() * 1000 即可得到）
            'timestamp': 0,
            # 签名: 需要我们自行构建
            'signature': '',
        }
        # 其他信息
        self.meta = {
            'login_url': 'https://www.zhihu.com/signup?next=%2F',
            'login_api': 'https://www.zhihu.com/api/v3/oauth/sign_in',
            'captcha_api': 'https://www.zhihu.com/api/v3/oauth/captcha?lang=',
            'old_login_api': 'https://www.zhihu.com/signup',
            # 可以在登录知乎时，在浏览器上打断点得到该信息
            'hmac_bstr': b'd1b964811afb40118a12068ff74a12f4',
        }

        self.form_data = form_info.copy()

        self.timestamp = int(time.time() * 1000)

        self.form_data.update({
            'timestamp': self.timestamp,
        })

        self.lang = self.form_data['lang']
        self.captcha_api = self.meta['captcha_api'] + self.lang
        yield scrapy.Request(
            url=self.captcha_api,
            headers=self.headers,
            callback=self._show_captcha,
        )

    def _show_captcha(self, response):
        """
        请求验证码的 API 接口，无论是否需要验证码都需要请求一次
        如果需要验证码会返回图片的 base64 编码
        根据 lang 参数匹配验证码，需要人工输入
        :param lang: 返回验证码的语言（en/cn）
        :return: 验证码的 POST 参数
        """

        show_captcha = re.search(r'true', response.body.decode('utf-8'))

        if show_captcha:
            yield scrapy.Request(
                url=self.captcha_api,
                method='put',
                headers=self.headers,
                callback=self._get_captcha,
            )

    def _get_captcha(self, response):
        json_data = json.loads(response.body)
        img_base64 = json_data['img_base64'].replace(r'\n', '')

        with open('./captcha.jpg', 'wb') as f:
            f.write(base64.b64decode(img_base64))
        img = Image.open('./captcha.jpg')
        if self.lang == 'cn':
            plt.imshow(img)
            print('点击所有倒立的汉字，在命令行中按回车提交')
            points = plt.ginput(7)
            self.captcha = json.dumps({
                'img_size': [200, 44],
                'input_points': [[i[0] / 2, i[1] / 2] for i in points],
            })
        else:
            img_thread = threading.Thread(target=img.show, daemon=True)
            img_thread.start()
            self.captcha = input('请输入图片里的验证码：')

        self.form_data.update({
            'captcha': self.captcha
        })

        yield scrapy.FormRequest(
            url=self.captcha_api,
            method='post',
            headers=self.headers,
            formdata={'input_text': self.captcha},
            callback=self._get_signature
        )

    def _get_signature(self, response):

        ha = hmac.new(self.meta['hmac_bstr'], digestmod=hashlib.sha1)
        client_id = self.form_data['client_id']
        grant_type = self.form_data['grant_type']
        source = self.form_data['source']
        timestamp = self.form_data['timestamp']

        ha.update(bytes((grant_type + client_id + source + str(timestamp)), 'utf-8'))

        self.form_data.update({
            'signature': ha.hexdigest()
        })

        self.headers.update({
            'accept-encoding': 'gzip, deflate, br',
            'Referer': 'https://www.zhihu.com',
            'content-type': 'application/x-www-form-urlencoded',
            'x-xsrftoken': self._get_xsrf(response),
            'x-zse-83': '3_1.1',
        })

        formdata = self._encrypt(self.form_data)

        login_api = self.meta['login_api']

        yield scrapy.Request(
            url=login_api,
            headers=self.headers,
            body=formdata,
            method='post',
            callback=self.after_login,
        )

    def _get_xsrf(self, response):
        cookies = response.request.headers.getlist('Cookie')
        if cookies:
            cookies = cookies[0].decode('utf-8')
            cookie_list = cookies.split(';')
            for cookie in cookie_list:
                key = cookie.split('=')[0].replace(' ', '')
                if key == '_xsrf':
                    return cookie.split('=')[1]
        raise AssertionError('获取 xsrf 失败')

    def after_login(self, response):
        if 'authentication failed' in response.body:
            self.logger.error('Login failed')
            return

    def parse_page(self, response):
        pass

    @staticmethod
    def _encrypt(form_data):
        with open('./encrypt.js') as f:
            js = execjs.compile(f.read())
            return js.call('Q', urlencode(form_data))