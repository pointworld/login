# 爬虫 - 登录

本质：通过构建 HTTP 请求，发送给 HTTP 服务器，获取响应信息

## 知乎登录

### 方式一

> 说明
- 方式一的代码是基于 [zkqian/Zhihu-Login](https://github.com/zkqiang/Zhihu-Login) 代码之上做的简单封装，若需了解更多原始代码和其他信息，请访问该链接
- 代码：https://github.com/pointworld/login/blob/master/zhihu/01/login.py
      
 
### 方式二

> 说明
- 直接通过 selenium 模拟登录（扫码方式），获取 cookies
- 代码：https://github.com/pointworld/login/blob/master/zhihu/02/login.py
