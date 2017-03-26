__author__ = 'powergx'
from flask import request, Response, session, render_template, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import json
import uuid
from datetime import datetime, timedelta

@app.route('/messagebox')
@requires_auth
def messagebox():
    user = session.get('user_info')

    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None

    msgs_key = 'user_messages:%s' % user.get('username')

    msg_box = list()
    show_read_all = False
    for b_msg_id in r_session.lrange(msgs_key, 0, -1):
        msg_key = 'user_message:%s' % b_msg_id.decode('utf-8')
        b_msg = r_session.get(msg_key)
        if b_msg is None:
            r_session.lrem(msgs_key, msg_key)
            continue

        msg = json.loads(b_msg.decode('utf-8'))
        if show_read_all or not msg.get('is_read'):
            show_read_all = True
        msg_box.append(msg)

    return render_template('messages.html', err_msg=err_msg, messages=msg_box, show_read_all=show_read_all)

@app.route('/message/action', methods=['POST'])
@requires_auth
def message_action():
    user = session.get('user_info')

    if request.form['btn'] is None:
        session['error_message'] = '参数错误'
        return redirect(url_for('messagebox'))

    msgs_key = 'user_messages:%s' % user.get('username')

    all_message = r_session.lrange(msgs_key, 0, -1)

    for val in request.form:
        if len(val) < 4 or val[0:3] != 'msg':
            continue

        msg_id = val[4:]
        if bytes(msg_id, 'utf-8') not in all_message:
            continue

        if request.form['btn'] == 'mark_as_read':
            msg_key = 'user_message:%s' % msg_id

            msg = json.loads(r_session.get(msg_key).decode('utf-8'))
            msg['is_read'] = True
            r_session.set(msg_key, json.dumps(msg))

        elif request.form['btn'] == 'delete':
            r_session.lrem(msgs_key, msg_id)
            msg_key = 'user_message:%s' % msg_id
            r_session.delete(msg_key)

    return redirect(url_for('messagebox'))

@app.route('/add_msg')
@requires_admin
def add_msg():
    return '功能已关闭'
    i = 0
    for b_username in r_session.smembers('users'):
        i += 1
        if i > 10000:
            break
        send_msg(b_username.decode('utf-8'), '新域名通知 crysadm.com！', '最好看的矿场监工有新的访问姿势:crysadm.com           <br /> <br />'
                                                                   '''<table class="table table-bordered">
                                                      <tbody>
                                                      <tr>

                                                        <td>国内用户</td>
                                 <td><a href="https://crysadm.com">crysadm.com</a></td>
                                                                          </tr>
                                                                          <tr>
                                                                              <td>海外用户</td>
                                                                              <td><a href="https://os.crysadm.com">os.crysadm.com</a></td>
                                                                          </tr>
                                                                          </tbody>
                                                                      </table>
                                                                      ''', expire=3600 * 24)
    return '发送成功'

@app.route('/delall_msg')
@requires_admin
def del_all_msg():
    for k in r_session.keys('user_messages:*'):
        r_session.delete(k.decode('utf-8'))
    return '删除成功'

def send_msg(username, subject, content, expire=3600 * 24 * 7):
    if bytes(username, 'utf-8') not in r_session.smembers('users'):
        return '找不到该用户。'
    msgs_key = 'user_messages:%s' % username
    msg_id = str(uuid.uuid1())
    msg = dict(id=msg_id, subject=subject, content=content,
               is_read=False, time=datetime.now().strftime('%Y-%m-%d %H:%M'))
    msg_key = 'user_message:%s' % msg_id
    r_session.setex(msg_key, json.dumps(msg), expire)
    r_session.lpush(msgs_key, msg_id)
    return '发送成功'
