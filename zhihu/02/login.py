import os
import pickle
import time

from selenium import webdriver


def get_cookies():
    try:
        browser = webdriver.Chrome()
        browser.get('https://www.zhihu.com/signin?next=%2F')
        time.sleep(2)
        # 扫码登录
        browser.execute_script("document.getElementsByTagName('Button')[8].click()")
        _ = input('请扫码登录后，再输入回车：')
        cookies = browser.get_cookies()
        with open(COOKIE_FILE, 'wb') as f:
            pickle.dump(cookies, f)
        browser.quit()
        return cookies
    except Exception as e:
        print(e)


def load_cookies():
    cookies = pickle.load(open(COOKIE_FILE, 'rb')) if os.path.exists(COOKIE_FILE) else get_cookies()
    return {cookie['name']: cookie['value'] for cookie in cookies}


if __name__ == '__main__':
    COOKIE_FILE = './cookies.txt'
    cookies = load_cookies()
    # 得到 cookies 后，就可以利用 cookies 做后续操作
    print(cookies)