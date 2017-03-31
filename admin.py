__author__ = 'powergx'
from flask import request, Response, session, render_template, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import json
from util import hash_password
import re
import random
from message import send_msg
from datetime import datetime

# 系统管理 => 用户管理
@app.route('/admin/user')
@requires_admin
def admin_user():
    recent_login_users = []
    users = list()

    for b_user in r_session.mget(*['user:%s' % name.decode('utf-8') for name in sorted(r_session.smembers('users'))]):
        if b_user is None:
            continue
        user = json.loads(b_user.decode('utf-8'))
        if user.get('login_as_time') is not None:
            if (datetime.now() - datetime.strptime(user.get('login_as_time'), '%Y-%m-%d %H:%M:%S')).days < 3:
                recent_login_users.append(user)
        user['is_online'] = r_session.exists('user:%s:is_online' % user.get('username'))
        users.append(user)

    return render_template('admin_user.html',
                           recent_login_users=sorted(recent_login_users, key=lambda k: k['login_as_time'],
                                                     reverse=True),
                           users=users)

# 系统管理 => 通知管理
@app.route('/admin/message')
@requires_admin
def admin_message():
    return render_template('admin_message.html')

# 系统管理 => 邀请管理
@app.route('/admin/invitation')
@requires_admin
def admin_invitation():
    pub_inv_codes = r_session.smembers('public_invitation_codes')

    inv_codes = r_session.smembers('invitation_codes')
    return render_template('admin_invitation.html', inv_codes=inv_codes, public_inv_codes=pub_inv_codes)

# 系统管理 => 邀请管理 => 生成邀请码
@app.route('/generate/inv_code', methods=['POST'])
@requires_admin
def generate_inv_code():
    _chars = "0123456789ABCDEF"
    r_session.smembers('invitation_codes')

    for i in range(0, 20 - r_session.scard('invitation_codes')):
        r_session.sadd('invitation_codes', ''.join(random.sample(_chars, 10)))

    return redirect(url_for('admin_invitation'))

# 系统管理 => 邀请管理 => 生成公开邀请码
@app.route('/generate/pub_inv_code', methods=['POST'])
@requires_admin
def generate_pub_inv_code():
    _chars = "0123456789ABCDEF"
    r_session.smembers('public_invitation_codes')

    for i in range(0, 10 - r_session.scard('public_invitation_codes')):
        key = ''.join(random.sample(_chars, 10))
        r_session.sadd('public_invitation_codes', key)

    return redirect(url_for('admin_invitation'))

# 系统管理 => 用户管理 => 登陆其它用户
@app.route('/admin/login_as/<username>', methods=['POST'])
@requires_admin
def generate_login_as(username):
    user_info = r_session.get('%s:%s' % ('user', username))

    user = json.loads(user_info.decode('utf-8'))
    user['login_as_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    r_session.set('%s:%s' % ('user', username), json.dumps(user))
    session['admin_user_info'] = session.get('user_info')
    session['user_info'] = user

    return redirect(url_for('dashboard'))

# 系统管理 => 用户管理 => 编辑用户资料
@app.route('/admin_user/<username>')
@requires_admin
def admin_user_management(username):

    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None

    user = json.loads(r_session.get('user:%s' % username).decode('utf-8'))

    return render_template('user_management.html', err_msg=err_msg, user=user)

# 系统管理 => 用户管理 => 编辑用户资料 => 修改密码
@app.route('/admin/change_password/<username>', methods=['POST'])
@requires_admin
def admin_change_password(username):
    n_password = request.values.get('new_password')

    if len(n_password) < 8:
        session['error_message'] = '输入的新密码必须8位数以上.'
        return redirect(url_for('admin_user_management', username=username))

    user_key = '%s:%s' % ('user', username)
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    user_info['password'] = hash_password(n_password)
    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for('admin_user_management', username=username))

# 系统管理 => 用户管理 => 编辑用户资料 => 修改其它属性
@app.route('/admin/change_property/<field>/<value>/<username>', methods=['POST'])
@requires_admin
def admin_change_property(field, value, username):
    user_key = '%s:%s' % ('user', username)
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    if field == 'is_admin':
        user_info['is_admin'] = True if value == '1' else False
    elif field == 'active':
        user_info['active'] = True if value == '1' else False
    elif field == 'auto_column':
        user_info['auto_column'] = True if value == '1' else False
    elif field == 'auto_collect':
        user_info['auto_collect'] = True if value == '1' else False
    elif field == 'auto_drawcash':
        user_info['auto_drawcash'] = True if value == '1' else False
    elif field == 'auto_giftbox':
        user_info['auto_giftbox'] = True if value == '1' else False
    elif field == 'auto_shakegift':
        user_info['auto_shakegift'] = True if value == '1' else False
    elif field == 'auto_searcht':
        user_info['auto_searcht'] = True if value == '1' else False
    elif field == 'auto_revenge':
        user_info['auto_revenge'] = True if value == '1' else False
    elif field == 'auto_getaward':
        user_info['auto_getaward'] = True if value == '1' else False

    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for('admin_user_management', username=username))

# 系统管理 => 用户管理 => 编辑用户资料 => 提示信息
@app.route('/admin/change_user_info/<username>', methods=['POST'])
@requires_admin
def admin_change_user_info(username):
    max_account_no = request.values.get('max_account_no')

    r = r"^[1-9]\d*$"
    if re.match(r, max_account_no) is None:
        session['error_message'] = '迅雷账号限制必须为整数.'
        return redirect(url_for('admin_user_management', username=username))

    if not 0 < int(max_account_no) < 101:
        session['error_message'] = '迅雷账号限制必须为 1~100.'
        return redirect(url_for('admin_user_management', username=username))

    user_key = '%s:%s' % ('user', username)
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    user_info['max_account_no'] = int(max_account_no)

    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for('admin_user_management', username=username))

# 系统管理 => 用户管理 => 删除用户
@app.route('/admin/del_user/<username>', methods=['GET'])
@requires_admin
def admin_del_user(username):
    if r_session.get('%s:%s' % ('user', username)) is None:
        session['error_message'] = '账号不存在'
        return redirect(url_for('admin_user', username=username))

    # do del user
    r_session.delete('%s:%s' % ('user', username))
    r_session.srem('users', username)
    for b_account_id in r_session.smembers('accounts:' + username):
        account_id = b_account_id.decode('utf-8')
        r_session.delete('account:%s:%s' % (username, account_id))
        r_session.delete('account:%s:%s:data' % (username, account_id))
    r_session.delete('accounts:' + username)

    for key in r_session.keys('user_data:%s:*' % username):
        r_session.delete(key.decode('utf-8'))

    for key in r_session.keys('record:%s:*' % username):
        r_session.delete(key.decode('utf-8'))

    return redirect(url_for('admin_user'))

# 系统管理 => 用户管理 => 无用户？
@app.route('/none_user')
@requires_admin
def none_user():
    none_xlAcct = list()
    none_active_xlAcct = list()
    for b_user in r_session.smembers('users'):
        username = b_user.decode('utf-8')

        if r_session.smembers('accounts:' + username) is None or len(r_session.smembers('accounts:' + username)) == 0:
            none_xlAcct.append(username)
        has_active_account = False
        for b_xl_account in r_session.smembers('accounts:' + username):
            xl_account = b_xl_account.decode('utf-8')
            account = json.loads(r_session.get('account:%s:%s' % (username, xl_account)).decode('utf-8'))
            if account.get('active'):
                has_active_account = True
                break
        if not has_active_account:
            none_active_xlAcct.append(username)

    return json.dumps(dict(none_xlAcct=none_xlAcct, none_active_xlAcct=none_active_xlAcct))

# 系统管理 => 用户管理 => 删除无用户？
@app.route('/del_none_user')
@requires_admin
def del_none_user():
    none_active_xlAcct = list()
    for b_user in r_session.smembers('users'):
        username = b_user.decode('utf-8')

        if r_session.smembers('accounts:' + username) is None or len(r_session.smembers('accounts:' + username)) == 0:
            admin_del_user(username)
        has_active_account = False
        for b_xl_account in r_session.smembers('accounts:' + username):
            xl_account = b_xl_account.decode('utf-8')
            account = json.loads(r_session.get('account:%s:%s' % (username, xl_account)).decode('utf-8'))
            if account.get('active'):
                has_active_account = True
                break
        if not has_active_account:
            none_active_xlAcct.append(username)

    return json.dumps(dict(none_active_xlAcct=none_active_xlAcct))

# 系统管理 => 通知管理 => 发送通知
@app.route('/admin/message/send', methods=['POST'])
@requires_admin
def admin_message_send():
    to = request.values.get('to')
    subject = request.values.get('subject')
    summary = request.values.get('summary')
    content = request.values.get('content')

    if subject == '':
        session['error_message'] = '标题为必填。'
        return redirect(url_for('admin_message'))

    if to == '':
        session['error_message'] = '收件方必填。'
        return redirect(url_for('admin_message'))

    if summary == '':
        session['error_message'] = '简介必填'
        return redirect(url_for('admin_message'))

    send_content = '{:<30}'.format(summary) + content
    if to == 'ALL':
        for b_username in r_session.smembers('users'):
            send_msg(b_username.decode('utf-8'), subject, send_content, 3600 * 24 * 7)

    else:
        send_msg(to, subject, send_content, 3600 * 24)

    return redirect(url_for('admin_message'))

# 关于
@app.route('/about')
@requires_auth
def about():
    return render_template('about.html')
