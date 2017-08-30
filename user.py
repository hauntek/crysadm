__author__ = 'powergx'
from flask import request, Response, session, render_template, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import json
from util import hash_password
import re
import uuid
from datetime import datetime, timedelta

@app.route('/guest')
def guest():
    user_info = r_session.get('%s:%s' % ('user', 'test'))
    if user_info is None:
        session['error_message'] = '用户不存在'
        return redirect(url_for('login'))

    user = json.loads(user_info.decode('utf-8'))

    if not user.get('active'):
        session['error_message'] = '访客账号已被禁用.'
        return redirect(url_for('login'))

    session['user_info'] = user

    return redirect(url_for('dashboard'))

@app.route('/login')
def login():
    session.permanent = False
    if session.get('user_info') is not None:
        return redirect(url_for('dashboard'))

    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None

    return render_template('login.html', err_msg=err_msg)

@app.route('/user/login', methods=['POST'])
def user_login():
    username = request.values.get('username')
    password = request.values.get('password')

    hashed_password = hash_password(password)

    user_info = r_session.get('%s:%s' % ('user', username))
    if user_info is None:
        session['error_message'] = '用户不存在'
        return redirect(url_for('login'))

    user = json.loads(user_info.decode('utf-8'))

    if user.get('password') != hashed_password:
        session['error_message'] = '密码错误'
        return redirect(url_for('login'))

    if not user.get('active'):
        session['error_message'] = '您的账号已被禁用.'
        return redirect(url_for('login'))

    session['user_info'] = user

    return redirect(url_for('dashboard'))

@app.route('/user/logout')
@requires_auth
def logout():
    if session.get('admin_user_info') is not None:
        session['user_info'] = session.get('admin_user_info')
        del session['admin_user_info']
        return redirect(url_for('admin_user'))

    session.clear()
    return redirect(url_for('login'))

@app.route('/diary')
@requires_auth
def diary():
    user = session.get('user_info')

    diary_as = list()

    today = datetime.now().date() + timedelta(days=-1)
    begin_date = today + timedelta(days=-7)
    while begin_date < datetime.now().date():
        begin_date += timedelta(days=1)
        key = 'record:%s:%s' % (user.get('username'), begin_date.strftime('%Y-%m-%d'))
        b_data = r_session.get(key)
        if b_data is None: continue
        today_data = json.loads(b_data.decode('utf-8')).get('diary')
        diary_as += today_data

    return render_template('diary.html', diary_user=sorted(diary_as, key=lambda x: x['time'], reverse=True))

@app.route('/diary/del')
@requires_auth
def diary_del():
    user = session.get('user_info')

    for key in r_session.keys('record:%s:*' % user.get('username')):
        r_session.delete(key.decode('utf-8'))

    return redirect(url_for('diary'))

@app.route('/talk')
@requires_auth
def user_talk():
    return render_template('talk.html')

@app.route('/user/profile')
@requires_auth
def user_profile():
    user = session.get('user_info')

    user_key = '%s:%s' % ('user', user.get('username'))
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None

    action = None
    if session.get('action') is not None:
        action = session.get('action')
        session['action'] = None

    return render_template('profile.html', user_info=user_info, err_msg=err_msg, action=action)

@app.route('/user/data/del', methods=['POST'])
@requires_auth
def user_data_del():
    user = session.get('user_info')

    for key in r_session.keys('user_data:%s:*' % user.get('username')):
        r_session.delete(key.decode('utf-8'))

    return redirect(url_for('user_profile'))

@app.route('/user/change_info', methods=['POST'])
@requires_auth
def user_change_info():
    user = session.get('user_info')

    email = request.values.get('email')
    session['action'] = 'info'

    r = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    if re.match(r, email) is None:
        session['error_message'] = '电子邮箱地址格式不正确.'
        return redirect(url_for('user_profile'))

    user_key = '%s:%s' % ('user', user.get('username'))
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    user_info['email'] = email
    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for('user_profile'))

@app.route('/user/change_property/<field>/<value>', methods=['POST'])
@requires_auth
def user_change_property(field, value):
    user = session.get('user_info')

    user_key = '%s:%s' % ('user', user.get('username'))
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))
    session['action'] = 'property'

    if field == 'auto_column':
        session['action'] = 'info'
        user_info['auto_column'] = True if value == '1' else False
    if field == 'auto_collect':
        user_info['auto_collect'] = True if value == '1' else False
    if field == 'auto_drawcash':
        user_info['auto_drawcash'] = True if value == '1' else False
    if field == 'auto_giftbox':
        user_info['auto_giftbox'] = True if value == '1' else False
    if field == 'auto_shakegift':
        user_info['auto_shakegift'] = True if value == '1' else False
    if field == 'auto_searcht':
        user_info['auto_searcht'] = True if value == '1' else False
    if field == 'auto_revenge':
        user_info['auto_revenge'] = True if value == '1' else False
    if field == 'auto_getaward':
        user_info['auto_getaward'] = True if value == '1' else False

    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for('user_profile'))

@app.route('/user/change_password', methods=['POST'])
@requires_auth
def user_change_password():
    user = session.get('user_info')

    old_password = request.values.get('old_password')
    session['action'] = 'password'

    user_key = '%s:%s' % ('user', user.get('username'))
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    hashed_password = hash_password(old_password)
    if user_info.get('password') != hashed_password:
        session['error_message'] = '原密码不正确.'
        return redirect(url_for('user_profile'))

    new_password = request.values.get('new_password')
    new2_password = request.values.get('new2_password')

    if new_password != new2_password:
        session['error_message'] = '两次输入的新密码不一致.'
        return redirect(url_for('user_profile'))

    if len(new_password) < 8:
        session['error_message'] = '输入的新密码必须8位数以上.'
        return redirect(url_for('user_profile'))

    user_info['password'] = hash_password(new_password)
    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for('user_profile'))

@app.route('/register')
def register():
    if session.get('user_info') is not None:
        return redirect(url_for('dashboard'))

    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None

    info_msg = None
    if session.get('info_message') is not None:
        info_msg = session.get('info_message')
        session['info_message'] = None

    invitation_code = ''
    if request.values.get('inv_code') is not None and len(request.values.get('inv_code')) > 0:
        invitation_code = request.values.get('inv_code')

    return render_template('register.html', err_msg=err_msg, info_msg=info_msg, invitation_code=invitation_code)

@app.route('/user/register', methods=['POST'])
def user_register():
    invitation_code = request.values.get('invitation_code')

    if not r_session.sismember('invitation_codes', invitation_code) and \
    not r_session.sismember('public_invitation_codes', invitation_code):
        session['error_message'] = '无效的邀请码。'
        return redirect(url_for('register'))

    username = request.values.get('username')
    password = request.values.get('password')
    re_password = request.values.get('re_password')

    if username == '':
        session['error_message'] = '用户名不能为空.'
        return redirect(url_for('register'))

    if r_session.get('%s:%s' % ('user', username)) is not None:
        session['error_message'] = '该用户名已存在.'
        return redirect(url_for('register'))

    r = r"^[a-zA-Z0-9_.+-]+$"
    if re.match(r, username) is None:
        session['error_message'] = '用户名含有非法字符.'
        return redirect(url_for('register'))

    if len(username) < 6 or len(username) > 20:
        session['error_message'] = '用户名长度6~20个字符.'
        return redirect(url_for('register'))

    if password != re_password:
        session['error_message'] = '两次输入的密码不一致.'
        return redirect(url_for('register'))

    if len(password) < 8:
        session['error_message'] = '输入的密码必须8位数以上.'
        return redirect(url_for('register'))

    r_session.srem('invitation_codes', invitation_code)
    r_session.srem('public_invitation_codes', invitation_code)

    user = dict(username=username, password=hash_password(password), id=str(uuid.uuid1()),
                active=True, is_admin=False, max_account_no=20,
                created_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    r_session.set('%s:%s' % ('user', username), json.dumps(user))
    r_session.sadd('users', username)

    session['info_message'] = '恭喜你，注册成功.'
    return redirect(url_for('register'))
