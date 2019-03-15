import base64
import hashlib
import hmac
import json
import re
import threading
import time
from urllib.parse import urlencode
from http import cookiejar

import execjs
import requests
from PIL import Image

import matplotlib
matplotlib.use('TkAgg')


class ZhihuAccount:
    """
    知乎登录
    """

    def __init__(self, headers_info: dict, form_info: dict, meta: dict):
        """
        实例化
        :param headers_info: HTTP 头信息
        :param form_info: 表单信息
        :param meta: 其他信息
        """
        self.com_headers = headers_info.get('com_headers', {})
        self.req_headers = headers_info.get('req_headers', {})
        self.res_headers = headers_info.get('res_headers', {})

        self.form_data = form_info
        self.meta = meta

        self.session = requests.Session()
        self.session.headers = dict(self.com_headers, **self.req_headers)
        self.session.cookies = cookiejar.LWPCookieJar(filename='./cookies.txt')

    def login(self, is_load_cookies: bool = True):
        """
        模拟登录知乎
        若在 PyCharm 下使用中文验证出现无法点击的问题，需要将
        Windows: PyCharm / Settings / Tools / Python Scientific / Show Plots in Toolwindow，取消勾选
        Mac: PyCharm / Preferences / Tools / Python Scientific / Show Plots in Toolwindow，取消勾选

        :param is_load_cookies: 是否读取上次保存的 Cookies
        :return bool
       """

        if is_load_cookies and self.load_cookies():
            print('读取 Cookies 文件')
            if self.check_login():
                print('登录成功')
                return True
            print('Cookies 已过期')

        self._check_user_pass()

        timestamp = int(time.time() * 1000)
        self.form_data.update({
            'captcha': self._get_captcha(),
            'timestamp': timestamp,
            'signature': self._get_signature(timestamp),
        })

        headers = self.session.headers.copy()
        headers.update({
            **self.res_headers,
            'x-xsrftoken': self._get_xsrf(),
        })

        data = self._encrypt(self.form_data)
        login_api = self.meta['login_api']
        response = self.session.post(login_api, data=data, headers=headers, verify=False)

        if 'error' in response.text:
            print(json.loads(response.text)['error'])
        if self.check_login():
            print('登录成功')
            return True
        print('登录失败')

        return False

    def load_cookies(self):
        """
        读取 Cookies 文件加载到 Session
        :return: bool
        """
        try:
            self.session.cookies.load(ignore_discard=True)
            return True
        except FileNotFoundError:
            return False

    def check_login(self):
        """
        检查登录状态，访问登录页面出现跳转，则说明已登录
        若登录成功，则保存当前 Cookies
        :return: bool
        """
        login_url = self.meta['old_login_api']
        response = self.session.get(login_url, allow_redirects=False, verify=False)
        if response.status_code == 302:
            self.session.cookies.save()
            return True
        return False

    def _check_user_pass(self):
        """
        检查用户名和密码是否已输入，若无则手动输入
        :return:
        """
        username = self.form_data['username']
        password = self.form_data['password']

        if not username:
            username = input('请输入手机号：')
            self.form_data['username'] = ('+86' + username) if username.isdigit() else username

        if not password:
            self.form_data['password'] = input('请输入密码：')

    def _get_captcha(self):
        """
        请求验证码的 API 接口，无论是否需要验证码都需要请求一次
        如果需要验证码会返回图片的 base64 编码
        根据 lang 参数匹配验证码，需要人工输入
        :param lang: 返回验证码的语言（en/cn）
        :return: 验证码的 POST 参数
        """
        lang = self.form_data['lang']
        api = self.meta['captcha_api'] + lang

        response = self.session.get(api, verify=False)
        show_captcha = re.search(r'true', response.text)

        if show_captcha:
            put_response = self.session.put(api, verify=False)
            json_data = json.loads(put_response.text)
            img_base64 = json_data['img_base64'].replace(r'\n', '')
            with open('./captcha.jpg', 'wb') as f:
                f.write(base64.b64decode(img_base64))
            img = Image.open('./captcha.jpg')
            if lang == 'cn':
                import matplotlib.pyplot as plt
                plt.imshow(img)
                print('点击所有倒立的汉字，在命令行中按回车提交')
                points = plt.ginput(7)
                capt = json.dumps({
                    'img_size': [200, 44],
                    'input_points': [[i[0] / 2, i[1] / 2] for i in points]
                })
            else:
                img_thread = threading.Thread(target=img.show, daemon=True)
                img_thread.start()
                capt = input('请输入图片里的验证码：')
            # 这里必须先把参数 POST 到验证码的接口
            self.session.post(api, data={'input_text': capt}, verify=False)
            return capt
        return ''

    def _get_signature(self, timestamp: int or str):
        """
        通过 Hmac 算法计算返回签名
        实际是几个固定字符串加时间戳
        :param timestamp: 时间戳
        :return: 签名
        """
        ha = hmac.new(self.meta['hmac_bstr'], digestmod=hashlib.sha1)

        client_id = self.form_data['client_id']
        grant_type = self.form_data['grant_type']
        source = self.form_data['source']

        ha.update(bytes((grant_type + client_id + source + str(timestamp)), 'utf-8'))

        return ha.hexdigest()

    def _get_xsrf(self):
        """
        从登录页面获取 xsrf
        :return: str
        """
        self.session.get('https://www.zhihu.com/', allow_redirects=False, verify=False)
        for c in self.session.cookies:
            if c.name == '_xsrf':
                return c.value
        raise AssertionError('获取 xsrf 失败')

    @staticmethod
    def _encrypt(form_data: dict):
        with open('./encrypt.js') as f:
            js = execjs.compile(f.read())
            return js.call('Q', urlencode(form_data))


if __name__ == '__main__':

    # 需要提交的头信息，可以通过抓包工具或浏览器控制台得到相关信息
    headers_info = {
        # 通用头
        'com_headers': {
            'Host': 'www.zhihu.com',
            'accept-encoding': 'gzip, deflate, br',
            'Referer': 'https://www.zhihu.com/',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 ' 
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
        'username': '',
        # 账号密码
        'password': '',
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
    meta = {
        'login_api': 'https://www.zhihu.com/api/v3/oauth/sign_in',
        'captcha_api': 'https://www.zhihu.com/api/v3/oauth/captcha?lang=',
        'old_login_api': 'https://www.zhihu.com/signup',
        # 可以在登录知乎时，在浏览器上打断点得到该信息
        'hmac_bstr': b'd1b964811afb40118a12068ff74a12f4',
    }

    account = ZhihuAccount(headers_info=headers_info, form_info=form_info, meta=meta)
    account.login(is_load_cookies=True)
