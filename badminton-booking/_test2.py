import requests, execjs, urllib.parse
from bs4 import BeautifulSoup

env = {}
with open(".env") as f:
    for line in f:
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            env[k] = v.strip().strip("\"'")

js = execjs.compile(open("ez.js").read())

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9",
})

r = s.get("https://tycg.zjnu.edu.cn", allow_redirects=True)
print("Step 1 URL:", r.url[:120])

soup = BeautifulSoup(r.text, "lxml")
salt = soup.find("input", {"id": "pwdEncryptSalt"}).get("value", "")
exe = soup.find("input", {"name": "execution"}).get("value", "")
print(f"Step 2: salt={salt[:20]} exe={exe}")

enc = js.call("encryptPassword", env["ZJNU_PASSWORD"], salt)
print(f"Step 3: enc={enc[:50]}...")

s.headers["Referer"] = r.url
s.headers["Origin"] = "https://authserver.zjnu.edu.cn"
data = {"username": env["ZJNU_USERNAME"], "password": enc,
        "captcha": "", "_eventId": "submit", "cllt": "userNameLogin",
        "dllt": "generalLogin", "lt": "", "execution": exe}
r = s.post(r.url, data=data, allow_redirects=True)
print(f"Step 4: URL={r.url[:120]} history={len(r.history)}")

fragment = urllib.parse.urlparse(r.url).fragment
if "?" in fragment:
    params = urllib.parse.parse_qs(fragment.split("?")[1])
    print("Token:", params.get("token", ["NONE"])[0][:80])
else:
    print("No token - login failed URL:", r.url[:120])
