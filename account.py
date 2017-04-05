__author__ = 'powergx'
from flask import request, Response, session, render_template, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import json
from util import md5
from login import login
from datetime import datetime

# 显示所有绑定的迅雷会员帐号
@app.route('/accounts')
@requires_auth
def accounts():
    user = session.get('user_info')

    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None

    accounts_key = 'accounts:%s' % user.get('username')

    account_s = list()
    for acct in sorted(r_session.smembers(accounts_key)):
        account_key = 'account:%s:%s' % (user.get('username'), acct.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))
        account_s.append(account_info)

    return render_template('accounts.html', err_msg=err_msg, accounts=account_s)

# 绑定一个新的迅雷会员帐号
@app.route('/account/add', methods=['POST'])
@requires_auth
def account_add():
    user = session.get('user_info')

    account_name = request.values.get('xl_username')
    password = request.values.get('xl_password')

    md5_password = md5(password)

    accounts_key = 'accounts:%s' % user.get('username')

    account_no = r_session.scard(accounts_key)
    if account_no is not None:
        user_key = '%s:%s' % ('user', user.get('username'))
        user_info = json.loads(r_session.get(user_key).decode('utf-8'))
        if account_no >= user_info.get('max_account_no'):
            session['error_message'] = '你的账号限制%d个账户。' % account_no
            return redirect(url_for('accounts'))

    login_result = login(account_name, md5_password, app.config.get('ENCRYPT_PWD_URL'))
    if login_result.get('errorCode') != 0:
        error_message = login_result.get('errorDesc')
        session['error_message'] = '登陆失败，错误信息：%s。' % error_message
        return redirect(url_for('accounts'))

    xl_session_id = login_result.get('sessionID')
    xl_nick_name = login_result.get('nickName')
    xl_user_name = login_result.get('userName')
    xl_user_id = str(login_result.get('userID'))
    xl_user_new_no = str(login_result.get('userNewNo'))
    xl_account_name = account_name
    xl_password = md5_password

    r_session.sadd(accounts_key, xl_user_id)

    account_key = 'account:%s:%s' % (user.get('username'), xl_user_id)
    xl_account_data = dict(session_id=xl_session_id, nick_name=xl_nick_name, username=xl_user_name,
                           user_id=xl_user_id, user_new_no=xl_user_new_no, account_name=xl_account_name,
                           password=xl_password, active=True, status='OK',
                           createdtime=datetime.now().strftime('%Y-%m-%d %H:%M'))
    r_session.set(account_key, json.dumps(xl_account_data))

    return redirect(url_for('accounts'))

# 删除绑定的迅雷会员帐号
@app.route('/account/del/<xl_id>', methods=['POST'])
@requires_auth
def account_del(xl_id):
    user = session.get('user_info')

    accounts_key = 'accounts:%s' % user.get('username')
    account_key = 'account:%s:%s' % (user.get('username'), xl_id)
    account_data_key = account_key + ':data'
    r_session.srem(accounts_key, xl_id)
    r_session.delete(account_key)
    r_session.delete(account_data_key)

    return redirect(url_for('accounts'))

# 停止一个已经绑定的迅雷会员帐号
@app.route('/account/inactive/<xl_id>', methods=['POST'])
@requires_auth
def account_inactive(xl_id):
    user = session.get('user_info')

    account_key = 'account:%s:%s' % (user.get('username'), xl_id)
    account_info = json.loads(r_session.get(account_key).decode("utf-8"))
    account_info['active'] = False
    r_session.set(account_key, json.dumps(account_info))

    return redirect(url_for('accounts'))

# 激活一个已经停止的迅雷会员帐号
@app.route('/account/active/<xl_id>', methods=['POST'])
@requires_auth
def account_activel(xl_id):
    user = session.get('user_info')

    account_key = 'account:%s:%s' % (user.get('username'), xl_id)
    account_info = json.loads(r_session.get(account_key).decode("utf-8"))
    account_info['active'] = True
    r_session.set(account_key, json.dumps(account_info))

    return redirect(url_for('accounts'))

# 停止所有已经绑定的迅雷会员帐号
@app.route('/account/inactive/all', methods=['POST'])
@requires_auth
def account_inactive_all():
    user = session.get('user_info')

    accounts_key = 'accounts:%s' % user.get('username')
    for acct in sorted(r_session.smembers(accounts_key)):
        account_key = 'account:%s:%s' % (user.get('username'), acct.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))
        account_info['active'] = False
        r_session.set(account_key, json.dumps(account_info))

    return redirect(url_for('accounts'))

# 激活所有已经停止的迅雷会员帐号
@app.route('/account/active/all', methods=['POST'])
@requires_auth
def account_activel_all():
    user = session.get('user_info')

    accounts_key = 'accounts:%s' % user.get('username')
    for acct in sorted(r_session.smembers(accounts_key)):
        account_key = 'account:%s:%s' % (user.get('username'), acct.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))
        account_info['active'] = True
        r_session.set(account_key, json.dumps(account_info))

    return redirect(url_for('accounts'))
