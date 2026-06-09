from datetime import datetime, timedelta
import json
import os
import re
from pathlib import Path
import time

import execjs
from lxml import etree

# 读取 .env 配置
DIR = Path(__file__).parent.resolve()
_env = {}
if (DIR / ".env").exists():
    for line in (DIR / ".env").read_text("utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            _env[k.strip()] = v.strip().strip("'\"").strip("'")
import re
from pathlib import Pathquests

# 读取JS文件内容
with open("ez.js", "r", encoding="utf-8") as f:
    js_code = f.read()

# 执行JS代码并获取全局变量
context = execjs.compile(js_code)

# ==================== Cookie 持久化 ====================
def load_cookies(session, cookie_file):
    """加载保存的cookie到session"""
    if os.path.exists(cookie_file):
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
            for cookie in cookies:
                session.cookies.set(
                    cookie["name"], cookie["value"],
                    domain=cookie["domain"], path=cookie["path"]
                )
        return True
    return False


def save_cookies(session, cookie_file):
    """保存session中的cookie到文件"""
    cookies = []
    for cookie in session.cookies:
        cookies.append({
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path
        })
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)


# ==================== Token 持久化 ====================
def load_token(token_file):
    """加载保存的token"""
    if os.path.exists(token_file):
        with open(token_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            saved_time = data.get("saved_at", "")
            token = data.get("token", "")
            if token:
                print(f"[+] 已加载保存的token (保存时间: {saved_time})")
                return token
    return None


def save_token(token, token_file):
    """保存token到文件"""
    data = {
        "token": token,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==================== 会话状态统一保存 ====================
def save_session_state(session, cookie_file, token, token_file):
    """统一保存cookie和token，确保两者同步"""
    save_cookies(session, cookie_file)
    if token:
        save_token(token, token_file)
    print("[+] 会话状态已保存 (cookie + token)")


# ==================== 登录态验证 ====================
def check_login_valid(session, service_url):
    """检查当前session是否已登录"""
    try:
        test_response = session.get(service_url, allow_redirects=True, timeout=10)
        if "统一身份认证" not in test_response.text and "登录" not in test_response.text:
            return True
    except Exception as e:
        print(f"[-] 登录态验证请求异常: {e}")
    return False


# 获取明天的日期，格式为 yyyy-mm-dd
def get_tomorrow_date():
    tomorrow = datetime.now() + timedelta(days=1)
    return tomorrow.strftime("%Y-%m-%d")


# 等待到指定时间
def wait_until_target_time(target_hour=6, target_minute=0):
    print(f"\n=== 等待到 {target_hour}:{target_minute:02d} 整点 ===")
    while True:
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        current_second = now.second

        if current_hour == target_hour and current_minute == target_minute and current_second == 0:
            print(f"[+] 到达目标时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            break
        elif current_hour > target_hour or (current_hour == target_hour and current_minute > target_minute):
            print(f"[-] 目标时间已过，当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            break
        else:
            target_seconds = target_hour * 3600 + target_minute * 60
            current_seconds = current_hour * 3600 + current_minute * 60 + current_second
            wait_seconds = target_seconds - current_seconds

            if wait_seconds > 60:
                print(f"距离目标时间还有 {wait_seconds} 秒...")
                time.sleep(min(wait_seconds - 60, 10))
            else:
                print(f"距离目标时间还有 {wait_seconds} 秒...")
                time.sleep(1)

    return datetime.now()


# 获取明天的日期
tomorrow_date = get_tomorrow_date()


# 预约结果发送到手机端
def sc_send(sendkey, title, desp="", options=None):
    if options is None:
        options = {}
    if sendkey.startswith("sctp"):
        match = re.match(r"sctp(\d+)t", sendkey)
        if match:
            num = match.group(1)
            url = f"https://{num}.push.ft07.com/send/{sendkey}.send"
        else:
            raise ValueError("Invalid sendkey format for sctp")
    else:
        url = f"https://sctapi.ftqq.com/{sendkey}.send"
    params = {
        "title": title,
        "desp": desp,
        **options
    }
    headers = {
        "Content-Type": "application/json;charset=utf-8"
    }
    response = requests.post(url, json=params, headers=headers)
    result = response.json()
    return result


data = {}
with open(os.path.join(os.path.dirname(__file__), ".env"), "r") as f:
    for line in f:
        key, value = line.strip().split("=")
        data[key] = value
key = data["SENDKEY"]


# ===================== 【需替换】抓包获取的核心配置 =====================
service_url = "https://tycg.zjnu.edu.cn"
sso_login_url = "http://authserver.zjnu.edu.cn:80/authserver/login?service=https%3A%2F%2Ftycg.zjnu.edu.cn%2Fapi%2Fcas_auth%2Fauth"
login_post_url = "http://authserver.zjnu.edu.cn:80/authserver/login?service=https%3A%2F%2Ftycg.zjnu.edu.cn%2Fapi%2Fcas_auth%2Fauth"
username = _env.get("ZJNU_USERNAME", "")
password = _env.get("ZJNU_PASSWORD", "")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Referer": sso_login_url,
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8",
    "Origin": "https://authserver.zjnu.edu.cn"
}
# ========================================================================

# 持久化文件路径
cookie_file = os.path.join(os.path.dirname(__file__), "cookies.json")
token_file = os.path.join(os.path.dirname(__file__), "token.json")

# 1. 创建会话对象，全程维持Cookie和会话状态
session = requests.Session()
session.headers.update(headers)

# ==================== 第一步：尝试恢复已有会话 ====================
login_needed = True
token = None

# 1.1 加载cookie
if load_cookies(session, cookie_file):
    print("[+] 已加载保存的cookie")
    # 验证cookie是否有效
    if check_login_valid(session, service_url):
        print("[+] Cookie有效，无需重新登录")
        # 验证请求可能刷新了cookie，立即保存
        save_cookies(session, cookie_file)
        login_needed = False
    else:
        print("[-] Cookie已过期，需要重新登录")
else:
    print("[-] 未找到保存的cookie，需要登录")

# 1.2 如果cookie有效，尝试加载token
if not login_needed:
    token = load_token(token_file)
    if token:
        print("[+] Token已加载，可直接进行预约")
    else:
        print("[!] Cookie有效但无token，将尝试提取新token")
else:
    print("[!] 需要完整登录流程")

# ==================== 第二步：执行登录（如需要）====================
def do_login(session):
    """执行CAS SSO登录，返回是否成功"""
    try:
        # 访问业务系统，触发重定向到SSO登录页，获取登录页HTML
        response = session.get(service_url, allow_redirects=True)
        login_html = response.text

        # 解析HTML，提取动态隐藏参数
        tree = etree.HTML(login_html)
        execution = tree.xpath('//input[@name="execution"]/@value')[0]
        pwdEncryptSalt = tree.xpath('//input[@id="pwdEncryptSalt"]/@value')[0]

        encrypt_password = context.call("encryptPassword", password, pwdEncryptSalt)
        print(f"[*] 加密后密码: {encrypt_password[:30]}...")

        login_data = {
            "username": username,
            "password": encrypt_password,
            "captcha": "",
            "_eventId": "submit",
            "cllt": "userNameLogin",
            "dllt": "generalLogin",
            "lt": "",
            "execution": execution
        }

        # 发送登录POST请求
        login_response = session.post(login_post_url, data=login_data, allow_redirects=True)

        # 验证登录是否成功
        if check_login_valid(session, service_url):
            print("[+] 登录成功！会话已维持")
            save_cookies(session, cookie_file)
            return True
        else:
            print("[-] 登录失败，检查参数、加密逻辑或账号密码")
            if "login_response" in dir():
                print("响应内容:", login_response.text[:500])
            return False
    except Exception as e:
        print(f"[-] 登录过程异常: {e}")
        return False


# ==================== 第三步：提取token ====================
def extract_token(session):
    """从场馆预约页面提取API token"""
    print("\n=== 访问场馆预约页面 ===")
    venue_url = "https://tycg.zjnu.edu.cn/venue"
    try:
        venue_response = session.get(venue_url, allow_redirects=True, timeout=10)
        print(f"场馆预约页面状态码: {venue_response.status_code}")

        token_match = re.search(r"token=([^&]+)", venue_response.url)
        if token_match:
            token = token_match.group(1)
            print(f"[+] 成功提取token: {token[:20]}...")
            save_token(token, token_file)
            return token
        else:
            print("[-] 未在URL中找到token参数")
            # 尝试从响应内容中提取
            token_match2 = re.search(r'"token"\s*:\s*"([^"]+)"', venue_response.text)
            if token_match2:
                token = token_match2.group(1)
                print(f"[+] 从响应内容中提取到token: {token[:20]}...")
                save_token(token, token_file)
                return token
            print("[-] 也无法从响应内容中提取token")
    except Exception as e:
        print(f"[-] 提取token异常: {e}")
    return None


# ==================== 主流程 ====================
try:
    # 如果需要登录，先登录
    if login_needed:
        if not do_login(session):
            ret = sc_send(key, "登录失败", "检查参数、加密逻辑或账号密码")
            exit(1)
        # 登录成功后提取token
        token = extract_token(session)

    # 如果没有token（cookie有效但token缺失），尝试提取
    if not token:
        print("[!] 尝试从已有会话提取token...")
        token = extract_token(session)

    if token:
        # 构建带token的请求头
        headers_with_token = headers.copy()
        headers_with_token["Authorization"] = token
        headers_with_token["Content-Type"] = "application/json"
        headers_with_token["Origin"] = "https://tycg.zjnu.edu.cn"
        headers_with_token["Referer"] = "https://tycg.zjnu.edu.cn/h5/index.html?v=4/"

        # 定义多个场地的参数
        venues = [
            {
                "goods_id": "87",
                "order_type": 3,
                "pay_way": "0",
                "other_param": '{"price_ids":"10617","time_ids":"1131","field_ids":"449","price":"0.00","court_id":"87","meal_id":156,"field_type":"1"}',
                "choose_date": tomorrow_date,
            },
            {
                "goods_id": "87",
                "order_type": 3,
                "pay_way": "0",
                "other_param": '{"price_ids":"10630","time_ids":"1131","field_ids":"450","price":"0.00","court_id":"87","meal_id":156,"field_type":"1"}',
                "choose_date": tomorrow_date,
            },
            {
                "goods_id": "87",
                "order_type": 3,
                "pay_way": "0",
                "other_param": '{"price_ids":"10643","time_ids":"1131","field_ids":"451","price":"0.00","court_id":"87","meal_id":156,"field_type":"1"}',
                "choose_date": tomorrow_date,
            },
            {
                "goods_id": "87",
                "order_type": 3,
                "pay_way": "0",
                "other_param": '{"price_ids":"10656","time_ids":"1131","field_ids":"452","price":"0.00","court_id":"87","meal_id":156,"field_type":"1"}',
                "choose_date": tomorrow_date,
            },
            {
                "goods_id": "87",
                "order_type": 3,
                "pay_way": "0",
                "other_param": '{"price_ids":"10669","time_ids":"1131","field_ids":"453","price":"0.00","court_id":"87","meal_id":156,"field_type":"1"}',
                "choose_date": tomorrow_date,
            },
            {
                "goods_id": "87",
                "order_type": 3,
                "pay_way": "0",
                "other_param": '{"price_ids":"10682","time_ids":"1131","field_ids":"454","price":"0.00","court_id":"87","meal_id":156,"field_type":"1"}',
                "choose_date": tomorrow_date,
            },
            {
                "goods_id": "87",
                "order_type": 3,
                "pay_way": "0",
                "other_param": '{"price_ids":"10695","time_ids":"1131","field_ids":"455","price":"0.00","court_id":"87","meal_id":156,"field_type":"1"}',
                "choose_date": tomorrow_date,
            },
            {
                "goods_id": "87",
                "order_type": 3,
                "pay_way": "0",
                "other_param": '{"price_ids":"10708","time_ids":"1131","field_ids":"456","price":"0.00","court_id":"87","meal_id":156,"field_type":"1"}',
                "choose_date": tomorrow_date,
            },
            {
                "goods_id": "87",
                "order_type": 3,
                "pay_way": "0",
                "other_param": '{"price_ids":"10721","time_ids":"1131","field_ids":"457","price":"0.00","court_id":"87","meal_id":156,"field_type":"1"}',
                "choose_date": tomorrow_date,
            }
        ]
        venue1 = {
            "goods_id": "84",
            "order_type": 3,
            "pay_way": "0",
            "other_param": '{"price_ids":"10280","time_ids":"1077","field_ids":"421","price":"0.00","court_id":"84","meal_id":152,"field_type":"1"}',
            "choose_date": tomorrow_date,
        }

        pay_api_url = "https://tycg.zjnu.edu.cn/api/pay/CreateOrder"
        venue = venues[0]

        # 等待到7点整
        print("\n=== 等待到7点整发送预约请求 ===")
        wait_until_target_time(7, 0)

        print(f"\n=== 尝试预约场地 ===")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"发送预约请求时间: {current_time}")

        max_retries = 10
        pay_response = None
        for attempt in range(max_retries):
            pay_response = session.post(pay_api_url, json=venue, headers=headers_with_token, allow_redirects=True)
            pay_response1 = session.post(pay_api_url, json=venue1, headers=headers_with_token, allow_redirects=True)
            print(f"第 {attempt + 1} 次请求状态码: {pay_response.status_code}")

            if pay_response.status_code != 502:
                break

            if attempt < max_retries - 1:
                time.sleep(0.1)

        print(f"提交预约状态码: {pay_response.status_code}")
        print(f"提交预约响应: {pay_response.text}")
        print(f"提交预约响应1: {pay_response1.text}")
        print(f"提交预约状态码1: {pay_response1.status_code}")

        # 检查响应内容
        if "成功" in pay_response.text:
            print(f"[+] 预约成功！")
            ret = sc_send(key, "预约成功", "。\n\n。")
        else:
            print("❌ 预约失败，场地已被锁定")
            ret = sc_send(key, "预约失败，场地已被锁定", "。\n\n。")
    else:
        print("[-] 未能获取token，请检查网络或登录状态")
        ret = sc_send(key, "未提取到token", "请检查网络或登录状态")

except Exception as e:
    print(f"请求出错：{str(e)}")
    ret = sc_send(key, "脚本运行异常", str(e))

