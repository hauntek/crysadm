__author__ = 'powergx'
from flask import request, Response, session, render_template, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import json
from urllib.parse import urlparse, parse_qs
import time
import threading

from api import *

# 加载矿机主页面
@app.route('/excavators')
@requires_auth
def excavators():
    user = session.get('user_info')

    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None

    info_msg = None
    if session.get('info_message') is not None:
        info_msg = session.get('info_message')
        session['info_message'] = None

    accounts_key = 'accounts:%s' % user.get('username')

    accounts = list()
    for acct in sorted(r_session.smembers(accounts_key)):
        account_key = 'account:%s:%s' % (user.get('username'), acct.decode("utf-8"))
        account_data_key = account_key + ':data'
        account_data_value = r_session.get(account_data_key)
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))
        if account_data_value is not None:
            account_info['data'] = json.loads(account_data_value.decode("utf-8"))
        accounts.append(account_info)

    show_drawcash = r_session.exists('can_drawcash')

    return render_template('excavators.html', err_msg=err_msg, info_msg=info_msg, accounts=accounts,
                           show_drawcash=show_drawcash)

# 正则过滤 + URL转码
def regular_html(info):
    import re
    from urllib.parse import unquote
    regular = re.compile('<[^>]+>')
    url = unquote(info)
    return regular.sub("", url)

# 收取水晶[id]
@app.route('/collect/<user_id>', methods=['POST'])
@requires_auth
def collect_id(user_id):
    user = session.get('user_info')

    account_key = 'account:%s:%s' % (user.get('username'), user_id)
    account_info = json.loads(r_session.get(account_key).decode("utf-8"))

    session_id = account_info.get('session_id')
    user_id = account_info.get('user_id')

    cookies = dict(sessionid=session_id, userid=str(user_id))
    r = collect(cookies)
    if r.get('rd') != 'ok':
        session['error_message'] = r.get('rd')
        return redirect(url_for('excavators'))
    else:
        session['info_message'] = '收取水晶成功.'
    account_data_key = account_key + ':data'
    account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
    account_data_value.get('mine_info')['td_not_in_a'] = 0
    r_session.set(account_data_key, json.dumps(account_data_value))

    return redirect(url_for('excavators'))

# 收取水晶[all]
@app.route('/collect/all', methods=['POST'])
@requires_auth
def collect_all():
    user = session.get('user_info')
    username = user.get('username')

    error_message = ''
    success_message = ''
    for b_user_id in r_session.smembers('accounts:%s' % username):

        account_key = 'account:%s:%s' % (username, b_user_id.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))

        session_id = account_info.get('session_id')
        user_id = account_info.get('user_id')

        cookies = dict(sessionid=session_id, userid=str(user_id))
        r = collect(cookies)
        if r.get('rd') != 'ok':
            error_message += 'Id:%s : %s<br />' % (user_id, r.get('rd'))
        else:
            success_message += 'Id:%s : 收取水晶成功.<br />' % user_id
            account_data_key = account_key + ':data'
            account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
            account_data_value.get('mine_info')['td_not_in_a'] = 0
            r_session.set(account_data_key, json.dumps(account_data_value))

    if len(success_message) > 0:
        session['info_message'] = success_message

    if len(error_message) > 0:
        session['error_message'] = error_message

    return redirect(url_for('excavators'))

# 秘银进攻[id]
@app.route('/searcht/<user_id>', methods=['POST'])
@requires_auth
def searcht_id(user_id):
    user = session.get('user_info')

    account_key = 'account:%s:%s' % (user.get('username'), user_id)
    account_info = json.loads(r_session.get(account_key).decode("utf-8"))

    session_id = account_info.get('session_id')
    user_id = account_info.get('user_id')

    cookies = dict(sessionid=session_id, userid=str(user_id))
    r = check_searcht(cookies)
    if r.get('r') != 0:
        session['error_message'] = regular_html(r.get('rd'))
        return redirect(url_for('excavators'))
    else:
        session['info_message'] = '获得:%s秘银.' % r.get('s')

    return redirect(url_for('excavators'))

# 秘银进攻[all]
@app.route('/searcht/all', methods=['POST'])
@requires_auth
def searcht_all():
    user = session.get('user_info')
    username = user.get('username')

    error_message = ''
    success_message = ''
    for b_user_id in r_session.smembers('accounts:%s' % username):

        account_key = 'account:%s:%s' % (username, b_user_id.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))

        session_id = account_info.get('session_id')
        user_id = account_info.get('user_id')

        cookies = dict(sessionid=session_id, userid=str(user_id))
        r = check_searcht(cookies)
        if r.get('r') != 0:
            error_message += 'Id:%s : %s<br />' % (user_id, regular_html(r.get('rd')))
        else:
            success_message += 'Id:%s : 获得:%s秘银.<br />' % (user_id, r.get('s'))

    if len(success_message) > 0:
        session['info_message'] = success_message

    if len(error_message) > 0:
        session['error_message'] = error_message

    return redirect(url_for('excavators'))

# 执行进攻函数
def check_searcht(cookies):
    t = api_sys_getEntry(cookies)
    if t.get('r') != 0:
        return dict(r='-1', rd='Forbidden')
    if t.get('steal_free') > 0:
        steal_info = api_steal_search(cookies)
        if steal_info.get('r') != 0:
            return steal_info
        r = api_steal_collect(cookies, steal_info.get('sid'))
        if r.get('r') != 0:
            return dict(r='-1', rd='Forbidden')
        api_steal_summary(cookies, steal_info.get('sid'))
        return r
    return dict(r='-1', rd='体力值为零')

# 幸运转盘[id]
@app.route('/getaward/<user_id>', methods=['POST'])
@requires_auth
def getaward_id(user_id):
    user = session.get('user_info')

    account_key = 'account:%s:%s' % (user.get('username'), user_id)
    account_info = json.loads(r_session.get(account_key).decode("utf-8"))

    session_id = account_info.get('session_id')
    user_id = account_info.get('user_id')

    cookies = dict(sessionid=session_id, userid=str(user_id))
    r = api_getaward(cookies)
    if r.get('rd') != 'ok':
        session['error_message'] = r.get('rd')
        return redirect(url_for('excavators'))
    else:
        session['info_message'] = '获得:%s  下次转需要:%s秘银.<br />' % (regular_html(r.get('tip')), r.get('cost'))

    return redirect(url_for('excavators'))

# 幸运转盘[all]
@app.route('/getaward/all', methods=['POST'])
@requires_auth
def getaward_all():
    user = session.get('user_info')
    username = user.get('username')

    error_message = ''
    success_message = ''
    for b_user_id in r_session.smembers('accounts:%s' % username):

        account_key = 'account:%s:%s' % (username, b_user_id.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))

        session_id = account_info.get('session_id')
        user_id = account_info.get('user_id')

        cookies = dict(sessionid=session_id, userid=str(user_id))
        r = api_getaward(cookies)
        if r.get('rd') != 'ok':
            error_message += 'Id:%s : %s<br />' % (user_id, r.get('rd'))
        else:
            success_message += 'Id:%s : 获得:%s  下次转需要:%s 秘银.<br />' % (user_id, regular_html(r.get('tip')), r.get('cost'))

    if len(success_message) > 0:
        session['info_message'] = success_message

    if len(error_message) > 0:
        session['error_message'] = error_message

    return redirect(url_for('excavators'))

# 用户提现[id]
@app.route('/drawcash/<user_id>', methods=['POST'])
@requires_auth
def drawcash_id(user_id):
    user = session.get('user_info')

    account_key = 'account:%s:%s' % (user.get('username'), user_id)
    account_info = json.loads(r_session.get(account_key).decode("utf-8"))

    session_id = account_info.get('session_id')
    user_id = account_info.get('user_id')

    cookies = dict(sessionid=session_id, userid=str(user_id))
    r = exec_draw_cash(cookies)
    if r.get('r') != 0:
        session['error_message'] = r.get('rd')
        return redirect(url_for('excavators'))
    else:
        session['info_message'] = r.get('rd')
    account_data_key = account_key + ':data'
    account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
    account_data_value.get('income')['r_can_use'] = 0
    r_session.set(account_data_key, json.dumps(account_data_value))

    return redirect(url_for('excavators'))

# 用户提现[all]
@app.route('/drawcash/all', methods=['POST'])
@requires_auth
def drawcash_all():
    user = session.get('user_info')
    username = user.get('username')

    error_message = ''
    success_message = ''
    for b_user_id in r_session.smembers('accounts:%s' % username):

        account_key = 'account:%s:%s' % (username, b_user_id.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))

        session_id = account_info.get('session_id')
        user_id = account_info.get('user_id')

        cookies = dict(sessionid=session_id, userid=str(user_id))
        r = exec_draw_cash(cookies)
        if r.get('r') != 0:
            error_message += 'Id:%s : %s<br />' % (user_id, r.get('rd'))
        else:
            success_message += 'Id:%s : %s<br />' % (user_id, r.get('rd'))
            account_data_key = account_key + ':data'
            account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
            account_data_value.get('income')['r_can_use'] = 0
            r_session.set(account_data_key, json.dumps(account_data_value))

    if len(success_message) > 0:
        session['info_message'] = success_message

    if len(error_message) > 0:
        session['error_message'] = error_message

    return redirect(url_for('excavators'))

# 暂停设备按钮
@app.route('/device/stop', methods=['POST'])
@requires_auth
def device_stop():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    ubus_cd(session_id, account_id, ["dcdn", "stop", {}], '&device_id=%s' % device_id)

    return redirect(url_for('excavators'))

# 启动设备按钮
@app.route('/device/start', methods=['POST'])
@requires_auth
def device_start():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    ubus_cd(session_id, account_id, ["dcdn", "start", {}], '&device_id=%s' % device_id)

    return redirect(url_for('excavators'))

# 升级设备按钮
@app.route('/device/upgrade', methods=['POST'])
@requires_auth
def device_upgrade():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    ubus_cd(session_id, account_id, ["upgrade", "start", {}], '&device_id=%s' % device_id)
    ubus_cd(session_id, account_id, ["upgrade", "get_progress", {}], '&device_id=%s' % device_id)
    # ubus_cd(session_id, account_id, ["upgrade", "check", {}], '&device_id=%s' % device_id)

    return redirect(url_for('excavators'))

# 重启设备按钮
@app.route('/device/reboot', methods=['POST'])
@requires_auth
def device_reboot():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    ubus_cd(session_id, account_id, ["mnt", "reboot", {}], '&device_id=%s' % device_id)

    return redirect(url_for('excavators'))

# 恢复出厂设置设备按钮
@app.route('/device/reset', methods=['POST'])
@requires_auth
def device_reset():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    ubus_cd(session_id, account_id, ["mnt", "reset", {}], '&device_id=%s' % device_id)

    return redirect(url_for('excavators'))

# 定位设备按钮
@app.route('/device/noblink', methods=['POST'])
@requires_auth
def device_noblink():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    threading.Thread(target=noblink, args=(device_id, session_id, account_id)).start()

    return redirect(url_for('excavators'))

def noblink(device_id, session_id, account_id):
    for i in range(10):
        ubus_cd(session_id, account_id, ["mnt", "noblink", {}], '&device_id=%s' % device_id)
        time.sleep(1)
        ubus_cd(session_id, account_id, ["mnt", "blink", {}], '&device_id=%s' % device_id)
        time.sleep(1)

# 生成设备名称
@app.route('/set_device_name', methods=['POST'])
@requires_auth
def set_device_name():
    setting_url = request.values.get('url')
    new_name = request.values.get('name')
    query_s = parse_qs(urlparse(setting_url).query, keep_blank_values=True)

    device_id = query_s['device_id'][0]
    session_id = query_s['session_id'][0]
    account_id = query_s['user_id'][0]

    ubus_cd(session_id, account_id, ["server", "set_device_name", {"device_name": new_name, "device_id": device_id}])

    return json.dumps(dict(status='success'))

# 加载设备页面
@app.route('/admin_device', methods=['POST'])
@requires_auth
def admin_device():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    action = None
    if session.get('action') is not None:
        action = session.get('action')
        session['action'] = None

    device_info = ubus_cd(session_id, account_id, ["server", "get_device", {"device_id": device_id}])

    return render_template('excavators_info.html', action=action, session_id=session_id, account_id=account_id, device_info=device_info)
