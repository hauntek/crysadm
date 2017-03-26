__author__ = 'powergx'
import requests
import random
import json
from util import md5, sha1
from urllib.parse import unquote, urlencode

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

rsa_mod = 0xAC69F5CCC8BDE47CD3D371603748378C9CFAD2938A6B021E0E191013975AD683F5CBF9ADE8BD7D46B4D2EC2D78AF146F1DD2D50DC51446BB8880B8CE88D476694DFC60594393BEEFAA16F5DBCEBE22F89D640F5336E42F587DC4AFEDEFEAC36CF007009CCCE5C1ACB4FF06FBA69802A8085C2C54BADD0597FC83E6870F1E36FD
rsa_pubexp = 0x010001

APP_VERSION = "1.0.0"
PROTOCOL_VERSION = 108

def cached(func):
    rsa_result = {}
    def _(s):
        if s in rsa_result:
            _r = rsa_result[s]
        else:
            _r = func(s)
            rsa_result[s] = _r
        return _r
    return _

def modpow(b, e, m):
    result = 1
    while (e > 0):
        if e & 1:
            result = (result * b) % m
        e = e >> 1
        b = (b * b) % m
    return result

def str_to_int(string):
    str_int = 0
    for i in range(len(string)):
        str_int = str_int << 8
        str_int += ord(string[i])
    return str_int

@cached
def rsa_encode(data):
    result = modpow(str_to_int(data), rsa_pubexp, rsa_mod)
    return "{0:0256X}".format(result) # length should be 1024bit, hard coded here

def long2hex(l):
    return hex(l)[2:].upper().rstrip('L')

def old_login(username, md5_password):

    hash_password = rsa_encode(md5_password)

    _chars = "0123456789ABCDEF"
    peer_id = ''.join(random.sample(_chars, 16))

    device_id = md5("%s23333" % md5_password) # just generate a 32bit string

    appName = 'com.xunlei.redcrystalandroid'
    md5_key = md5('C2049664-1E4A-4E1C-A475-977F0E207C9C')

    device_sign = 'div100.%s%s' % (device_id, md5(sha1("%s%s%s%s" % (device_id, appName, 61, md5_key))))

    payload = json.dumps({
        "protocolVersion": PROTOCOL_VERSION,
        "sequenceNo": 1000001,
        "platformVersion": 1,
        "peerID": peer_id,
        "businessType": 61,
        "clientVersion": APP_VERSION,
        "isCompressed": 0,
        "cmdID": 1,
        "userName": username,
        "passWord": hash_password,
        "loginType": 0,
        "sessionID": "",
        "verifyKey": "",
        "verifyCode": "",
        "appName": "ANDROID-%s" % appName,
        "devicesign": device_sign,
        "sdkVersion": 177588,
        "rsaKey": {
            "e": "%06X" % rsa_pubexp,
            "n": long2hex(rsa_mod)
        },
        "extensionList": ""
    })

    headers = {'User-Agent': "Mozilla/5.0 (iPhone; CPU iPhone OS 5_1 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Mobile/9B176 MicroMessenger/4.3.2"}
    r = requests.post("https://login.mobile.reg2t.sandai.net:443/", data=payload, headers=headers, verify=False)

    login_status = json.loads(r.text)

    return login_status

def login(username, md5_password, encrypt_pwd_url=None):
    if encrypt_pwd_url is None or encrypt_pwd_url == '':
        return old_login(username, md5_password)

    xunlei_domain = 'login.xunlei.com'
    s = requests.Session()
    r = s.get('http://%s/check/?u=%s&v=100' % (xunlei_domain, username))
    if r.cookies.get('check_n') is None:
        xunlei_domain = 'login2.xunlei.com'
        r = s.get('http://%s/check/?u=%s&v=100' % (xunlei_domain, username))

    if r.cookies.get('check_n') is None:
        return old_login(username, md5_password)
    check_n = unquote(r.cookies.get('check_n'))
    check_e = unquote(r.cookies.get('check_e'))
    check_result = unquote(r.cookies.get('check_result'))

    need_captcha = check_result.split(':')[0]
    if need_captcha == '1':
        return old_login(username, md5_password)
    captcha = check_result.split(':')[1].upper()

    params = dict(password=md5_password, captcha=captcha, check_n=check_n, check_e=check_e)

    r = requests.get(encrypt_pwd_url + '?' + urlencode(params))
    e_pwd = r.text
    if r.text == 'false':
        return old_login(username, md5_password)

    data = dict(business_type='100', login_enable='0', verifycode=captcha, v='100', e=check_e, n=check_n, u=username,
                p=e_pwd)
    r = s.post('http://%s/sec2login/' % xunlei_domain, data=data)

    cookies = r.cookies.get_dict()
    if len(cookies) < 5:
        return old_login(username, md5_password)

    return dict(errorCode=0, sessionID=cookies.get('sessionid'), nickName=cookies.get('usernick'),
                userName=cookies.get('usrname'), userID=cookies.get('userid'), userNewNo=cookies.get('usernewno'))
