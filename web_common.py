__author__ = 'powergx'
from flask import request, Response, session, render_template, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import json
import socket
import struct
from datetime import datetime, timedelta

# 获取前一日收益
def __get_yesterday_pdc(username):
    today = datetime.now()
    month_start_date = datetime(year=today.year, month=today.month, day=1).date()
    week_start_date = (today + timedelta(days=-today.weekday())).date()
    begin_date = month_start_date if month_start_date < week_start_date else week_start_date
    begin_date = begin_date + timedelta(days=-1)

    yesterday_m_pdc = 0
    yesterday_w_pdc = 0

    while begin_date < today.date():
        begin_date = begin_date + timedelta(days=1)

        key = 'user_data:%s:%s' % (username, begin_date.strftime('%Y-%m-%d'))

        b_data = r_session.get(key)
        if b_data is None:
            continue

        history_data = json.loads(b_data.decode('utf-8'))
        if begin_date >= month_start_date:
            yesterday_m_pdc += history_data.get('pdc')
        if begin_date >= week_start_date:
            yesterday_w_pdc += history_data.get('pdc')

    return yesterday_m_pdc, yesterday_w_pdc

# 显示控制面板
@app.route('/dashboard')
@requires_auth
def dashboard():
    return render_template('dashboard.html')

# 刷新控制面板数据
@app.route('/dashboard_data')
@requires_auth
def dashboard_data():
    user = session.get('user_info')
    username = user.get('username')

    key = 'user_data:%s:%s' % (username, datetime.now().strftime('%Y-%m-%d'))

    b_data = r_session.get(key)
    if b_data is None:
        empty_data = {
            'updated_time': '2015-01-01 00:00:00',
            'm_pdc': 0,
            'last_speed': 0,
            'deploy_speed' : 0,
            'w_pdc': 0,
            'yesterday_m_pdc': 0,
            'speed_stat': [],
            'yesterday_w_pdc': 0,
            'pdc': 0,
            'box_pdc': 0,
            'balance': 0,
            'income': 0
        }
        return Response(json.dumps(dict(today_data=empty_data)), mimetype='application/json')

    today_data = json.loads(b_data.decode('utf-8'))
    need_save = False
    if today_data.get('yesterday_m_pdc') is None or today_data.get('yesterday_w_pdc') is None:
        yesterday_m_pdc, yesterday_w_pdc = __get_yesterday_pdc(username)
        today_data['yesterday_m_pdc'] = yesterday_m_pdc
        today_data['yesterday_w_pdc'] = yesterday_w_pdc
        need_save = True

    today_data['m_pdc'] = today_data.get('yesterday_m_pdc') + today_data.get('pdc')
    today_data['w_pdc'] = today_data.get('yesterday_w_pdc') + today_data.get('pdc')

    if need_save:
        r_session.set(key, json.dumps(today_data))

    return Response(json.dumps(dict(today_data=today_data)), mimetype='application/json')

# 刷新控制面板图表速度数据
@app.route('/dashboard/speed_share')
@requires_auth
def dashboard_speed_share():
    user = session.get('user_info')
    username = user.get('username')

    drilldown_data = []
    for user_id in sorted(r_session.smembers('accounts:%s' % username)):

        account_data_key = 'account:%s:%s:data' % (username, user_id.decode('utf-8'))
        b_data = r_session.get(account_data_key)
        if b_data is None:
            continue
        data = json.loads(b_data.decode('utf-8'))

        mid = str(data.get('privilege').get('mid'))

        total_speed = 0
        device_speed = []
        for device in data.get('device_info'):
            if device.get('status') != 'online': continue
            uploadspeed = int(int(device.get('dcdn_upload_speed')) / 1024)
            total_speed += uploadspeed

            device_speed.append(dict(name=device.get('device_name'), value=uploadspeed))

        drilldown_data.append(dict(name='矿主ID:' + mid, value=total_speed, drilldown_data=device_speed))

    return Response(json.dumps(dict(data=drilldown_data)), mimetype='application/json')

# 显示控制面板速度详情
@app.route('/dashboard/speed_detail')
@requires_auth
def dashboard_speed_detail():
    user = session.get('user_info')
    username = user.get('username')

    device_speed = []
    for user_id in sorted(r_session.smembers('accounts:%s' % username)):

        account_data_key = 'account:%s:%s:data' % (username, user_id.decode('utf-8'))
        b_data = r_session.get(account_data_key)
        if b_data is None:
            continue
        data = json.loads(b_data.decode('utf-8'))

        for device in data.get('device_info'):
            if device.get('status') != 'online': continue
            upload_speed = int(int(device.get('dcdn_upload_speed')) / 1024)
            deploy_speed = int(device.get('dcdn_download_speed') / 1024)

            device_speed.append(dict(name=device.get('device_name'), upload_speed=upload_speed, deploy_speed=deploy_speed))

    device_speed = sorted(device_speed, key=lambda k: k.get('name'))

    categories = []
    upload_series = dict(name='上传速度', data=[], pointPadding=0.3, pointPlacement=-0.2)
    deploy_series = dict(name='下载速度', data=[], pointPadding=0.4, pointPlacement=-0.2)
    for d_s in device_speed:
        categories.append(d_s.get('name'))
        upload_series.get('data').append(d_s.get('upload_speed'))
        deploy_series.get('data').append(d_s.get('deploy_speed'))

    return Response(json.dumps(dict(categories=categories, series=[upload_series, deploy_series])), mimetype='application/json')

# 刷新今日收益
@app.route('/dashboard/today_income_share')
@requires_auth
def dashboard_today_income_share():
    user = session.get('user_info')
    username = user.get('username')

    pie_data = []
    for user_id in sorted(r_session.smembers('accounts:%s' % username)):

        account_data_key = 'account:%s:%s:data' % (username, user_id.decode('utf-8'))
        b_data = r_session.get(account_data_key)
        if b_data is None:
            continue
        data = json.loads(b_data.decode('utf-8'))

        mid = str(data.get('privilege').get('mid'))

        total_value = 0
        this_pdc = data.get('mine_info').get('dev_m').get('pdc')
        total_value += this_pdc

        pie_data.append(dict(name='矿主ID:' + mid, y=total_value))

    return Response(json.dumps(dict(data=pie_data)), mimetype='application/json')

# 同比产量
@app.route('/dashboard/DoD_income')
@requires_auth
def dashboard_DoD_income():
    user = session.get('user_info')

    user_key = 'user:%s' % user.get('username')
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))
    if not user_info.get('auto_column'):
        dod_income = DoD_income_yuanjiangong()
    else:
        dod_income = DoD_income_xunlei(True)

    return dod_income

# 默认统计
def DoD_income_yuanjiangong():
    user = session.get('user_info')
    username = user.get('username')

    key = 'user_data:%s:%s' % (username, 'income.history')

    b_income_history = r_session.get(key)
    if b_income_history is None:
        return Response(json.dumps(dict(data=[])), mimetype='application/json')

    income_history = json.loads(b_income_history.decode('utf-8'))

    today_series = dict(name='今日', data=[], pointPadding=0.2, pointPlacement=0, color='#676A6C')
    yesterday_series = dict(name='昨日', data=[], pointPadding=-0.1, pointPlacement=0, color='#1AB394')

    now = datetime.now()
    today_data = income_history.get(now.strftime('%Y-%m-%d'))
    yesterday_data = income_history.get((now + timedelta(days=-1)).strftime('%Y-%m-%d'))

    yesterday_last_value = 0
    today_data_last_value = 0
    for i in range(0, 24):
        hour = '%02d' % i
        yesterday_value = 0
        today_data_value = 0
        yesterday_next_value = 0
        if yesterday_data is not None:
            next_data = yesterday_data.get('%02d' % (i + 1))
            if yesterday_data.get('%02d' % (i + 1)) is not None:
                yesterday_next_value = sum(row['pdc'] for row in next_data)
            if yesterday_data.get(hour) is not None:
                yesterday_value = sum(row['pdc'] for row in yesterday_data.get(hour))
            else:
                if yesterday_next_value != 0:
                    yesterday_value = int((yesterday_next_value - yesterday_last_value) / 2) + \
                                      yesterday_last_value
                else:
                    yesterday_value = yesterday_last_value

        yesterday_series['data'].append(yesterday_value - yesterday_last_value)
        yesterday_last_value = yesterday_value

        if i >= now.hour:
            continue

        if today_data is not None and today_data.get(hour) is not None:
            today_data_value = sum(row['pdc'] for row in today_data.get(hour))

        if today_data_value != 0:
            today_series['data'].append(today_data_value - today_data_last_value)

            today_data_last_value = today_data_value
        else:
            today_series['data'].append(0)

    now_income_value = sum(today_series['data'][0:now.hour])
    dod_income_value = sum(yesterday_series['data'][0:now.hour])

    expected_income = '-'
    if dod_income_value > 0:
        expected_income = str(int((yesterday_last_value / dod_income_value) * now_income_value))

    dod_income_value += int((yesterday_series['data'][now.hour]) / 60 * now.minute)
    return Response(json.dumps(dict(series=[yesterday_series, today_series],
                                    data=dict(last_day_income=yesterday_last_value, dod_income_value=dod_income_value,
                                              expected_income=expected_income)
                                    )), mimetype='application/json')

# 迅雷统计
def DoD_income_xunlei(open_speeds):
    user = session.get('user_info')
    username = user.get('username')

    now = datetime.now()

    today_series = dict(name='今日', data=[], pointPadding=0.2, pointPlacement=0, color='#676A6C', yAxis=0)
    yesterday_series = dict(name='昨日', data=[], pointPadding=-0.1, pointPlacement=0, color='#1AB394', yAxis=0)
    today_speed_series = dict(name='今日', data=[], pointPadding=0.2, pointPlacement=0, color='#F15C80', type='spline', tooltip=dict(valueSuffix=' kbps'), yAxis=1)
    yesterday_speed_series = dict(name='昨日', data=[], pointPadding=-0.1, pointPlacement=0, color='#00B2EE',type='spline', tooltip=dict(valueSuffix=' kbps'), yAxis=1)

    key = 'user_data:%s:%s' % (username, now.strftime('%Y-%m-%d'))

    b_today_data_new = r_session.get(key)
    if b_today_data_new is None:
        today_series['data'] = [0] * 24
        today_speed_series['data'] = [0] * 24
    else:
        today_data = json.loads(b_today_data_new.decode('utf-8'))
        for i in range(24-now.hour, 25):
            temp = 0
            for hourly_produce in today_data.get('produce_stat'):
                temp +=  hourly_produce.get('hourly_list')[i]
            today_series['data'].append(temp)
        today_speed_data = today_data.get('speed_stat')
        for i in range(0, 24):
            if i + now.hour < 24:
                continue
            if today_speed_data is None:
                today_speed_series['data'] = []
            else:
                today_speed_series['data'].append(sum(row.get('dev_speed')[i] for row in today_speed_data))
        today_speed_series['data'].append(today_data.get('last_speed')*8)

    key = 'user_data:%s:%s' % (username, (now + timedelta(days=-1)).strftime('%Y-%m-%d'))

    b_yesterday_data_new = r_session.get(key)
    if b_yesterday_data_new is None:
        yesterday_series['data'] = [0] * 24
        yesterday_speed_series['data'] = [0] * 24
    else:
        yesterday_data = json.loads(b_yesterday_data_new.decode('utf-8'))
        for i in range(1, 25):
            if yesterday_data.get('produce_stat') is None: break
            temp = 0
            for hourly_produce in yesterday_data.get('produce_stat'):
                temp += hourly_produce.get('hourly_list')[i]
            yesterday_series['data'].append(temp)
        yesterday_speed_data = yesterday_data.get('speed_stat')
        for i in range(0, 24):
            if yesterday_speed_data is None:
                yesterday_speed_series['data'] = []
            else:
                yesterday_speed_series['data'].append(sum(row.get('dev_speed')[i] for row in yesterday_speed_data))

    now_income_value = sum(today_series['data'][0:now.hour])
    dod_income_value = sum(yesterday_series['data'][0:now.hour])

    yesterday_last_value = sum(yesterday_series['data'][:])

    expected_income = '-'
    if dod_income_value > 0:
        expected_income = str(int((yesterday_last_value / dod_income_value) * now_income_value))

    if len(yesterday_series['data']) != 0:
        dod_income_value += int((yesterday_series['data'][now.hour]) / 60 * now.minute)
    set_series = [yesterday_series, today_series]
    if open_speeds: set_series += [yesterday_speed_series, today_speed_series]
    return Response(json.dumps(dict(series=set_series,
                                    data=dict(last_day_income=yesterday_last_value, dod_income_value=dod_income_value,
                                              expected_income=expected_income)
                                    )), mimetype='application/json')

# 显示登录界面
@app.route('/')
def index():
    return redirect(url_for('login'))

# 显示crysadm管理员界面（初次登录）
@app.route('/install')
def install():
    import random, uuid
    from util import hash_password

    if r_session.scard('users') == 0:
        _chars = "0123456789ABCDEF"
        username = ''.join(random.sample(_chars, 6))
        password = ''.join(random.sample(_chars, 6))

        user = dict(username=username, password=hash_password(password), id=str(uuid.uuid1()),
                    active=True, is_admin=True, max_account_no=5,
                    created_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        r_session.set('%s:%s' % ('user', username), json.dumps(user))
        r_session.sadd('users', username)
        return 'username:%s,password:%s' % (username, password)

    return redirect(url_for('login'))

# 添加用户
@app.context_processor
def add_function():
    def convert_to_yuan(crystal_values):
        if crystal_values >= 10000:
            return str(int(crystal_values / 1000) / 10) + '元'
        return str(crystal_values) + '个'

    # 获取设备类型
    def get_device_type(device_code, model_code):
        if device_code == 421:
            return model_code
        elif device_code == 321:
            return model_code
        return '不知道'

    # 获取设备密码
    def get_device_root(sn, mac):
        import hashlib
        import base64
        key = '%s%s%s' % (sn, mac, 'i8e%Fvj24nz024@d!c')
        md5 = hashlib.md5(key.encode('utf-8')).digest()
        passwd = base64.b64encode(md5).decode('utf-8')
        passwd = passwd[0:8]
        passwd = passwd.replace('+', '-')
        passwd = passwd.replace('/', '_')
        return passwd

    def int2ip(int_ip):
        return socket.inet_ntoa(struct.pack("I", int_ip))

    return dict(convert_to_yuan=convert_to_yuan, get_device_type=get_device_type, get_device_root=get_device_root, int2ip=int2ip)

# 显示消息框
@app.context_processor
def message_box():
    if session is None or session.get('user_info') is None:
        return dict()
    user = session.get('user_info')

    msgs_key = 'user_messages:%s' % user.get('username')

    msg_box = list()
    msg_count = 0
    for b_msg_id in r_session.lrange(msgs_key, 0, -1):
        msg_key = 'user_message:%s' % b_msg_id.decode('utf-8')
        b_msg = r_session.get(msg_key)
        if b_msg is None:
            r_session.lrem(msgs_key, msg_key)
            continue

        msg = json.loads(b_msg.decode('utf-8'))
        if msg.get('is_read'):
            continue

        if len(msg.get('content')) > 41:
            msg['content'] = msg.get('content')[:30] + '...'
        else:
            msg['content'] = msg.get('content')[:30]
        msg_count += 1
        if not len(msg_box) > 3:
            msg_box.append(msg)

    return dict(msg_box=msg_box, msg_count=msg_count)


@app.context_processor
def header_info():
    if session is None or session.get('user_info') is None:
        return dict()
    user = session.get('user_info')

    key = 'user_data:%s:%s' % (user.get('username'), datetime.now().strftime('%Y-%m-%d'))

    data = dict(balance=0, refreshes=0)

    b_data = r_session.get(key)
    if b_data is not None:
        data['balance'] = json.loads(b_data.decode('utf-8')).get('balance')
        data['refreshes'] = json.loads(b_data.decode('utf-8')).get('refreshes')

    b_api_error_info = r_session.get('api_error_info')
    if b_api_error_info is not None:
        data['api_error_info'] = b_api_error_info.decode('utf-8')

    return data
