__author__ = 'powergx'
from flask import render_template, session, Response
from crysadm import app, r_session
from auth import requires_auth
import time
import json
from datetime import datetime, timedelta

def __get_speed_stat_chart_data(speed_stat_data):
    now = datetime.now()
    speed_stat_category = list()
    speed_stat_value = list()
    for i in range(-24, 0):
        speed_stat_category.append('%d:00' % (now + timedelta(hours=i + 1)).hour)

    for speed_data in speed_stat_data:
        this_data = dict(name='矿主ID:' + str(speed_data.get('mid')), data=list())
        speed_stat_value.append(this_data)

        dev_speed = speed_data.get('dev_speed')

        for i in range(0, 24):
            this_data.get('data').append(dev_speed[i] / 8)

    return dict(category=speed_stat_category, value=speed_stat_value)

def __get_history_speed_data(username):
    today = datetime.now().date() + timedelta(days=-1)
    begin_date = today + timedelta(days=-7)

    value = list()
    while begin_date < today:
        begin_date = begin_date + timedelta(days=1)
        str_date = begin_date.strftime('%Y-%m-%d')
        key = 'user_data:%s:%s' % (username, str_date)

        b_data = r_session.get(key)
        if b_data is None:
            continue
        history_data = json.loads(b_data.decode('utf-8'))

        day_speed = list()
        day_speed.append([0] * 24)
        for account in history_data.get('speed_stat'):
            day_speed.append(account.get('dev_speed'))
        value.append(dict(name=str_date, data=[x / 8 for x in [sum(i) for i in zip(*day_speed)]]))

    return value

def __get_speed_comparison_data(history_data, today_data, str_updated_time):
    category = list()

    value = list()

    value += history_data if len(history_data) < 7 else history_data[-6:]
    for i in range(1, 25):
        if i == 24:
            i = 0
        category.append('%d:00' % i)

    updated_time = datetime.strptime(str_updated_time, '%Y-%m-%d %H:%M:%S')
    if updated_time.date() == datetime.today().date() and updated_time.hour != 0:
        day_speed = list()
        for account in today_data:
            day_speed.append(account.get('dev_speed'))

        total_speed = [x / 8 for x in [sum(i) for i in zip(*day_speed)]][0 - updated_time.hour:]
        value.append(dict(name='今天', data=total_speed))

    return dict(category=category, value=value)

def __seven_day_pdc(username):
    history_speed = __get_history_speed_data(username)
    today = datetime.now().date() + timedelta(days=-1)
    begin_date = today + timedelta(days=-7)

    dict_history_speed = dict()
    for speed in history_speed:
        dict_history_speed[speed.get('name')] = int(sum(speed.get('data')) / 24)

    speed_column_value = list()
    category = list()
    income_value = dict(history_pdc=[])
    i = -1
    while begin_date < today:
        i += 1
        begin_date = begin_date + timedelta(days=1)
        str_date = begin_date.strftime('%Y-%m-%d')
        key = 'user_data:%s:%s' % (username, str_date)
        category.append(str_date)

        if str_date in dict_history_speed:
            speed_column_value.append(dict_history_speed.get(str_date))
        else:
            speed_column_value.append(0)

        b_data = r_session.get(key)
        if b_data is None:
            income_value.get('history_pdc').append(0)
            continue

        history_data = json.loads(b_data.decode('utf-8'))

        if history_data.get('pdc_detail') is not None:
            for pdc_info in history_data.get('pdc_detail'):
                mid = str(pdc_info.get('mid'))
                if mid in income_value:
                    income_value.get(mid).append(pdc_info.get('pdc'))
                else:
                    income_value[mid] = [0] * i + [pdc_info.get('pdc')]
        else:
            income_value.get('history_pdc').append(history_data.get('pdc'))

        for key in income_value:
            if len(income_value[key]) <= i:
                income_value[key] = income_value[key]+[0]

    series = []

    for key in sorted(income_value, reverse=True):
        value = income_value[key]
        if len(value) < 7:
            value += [0] * (7 - len(value))
        name = ''
        if key == 'history_pdc':
            name = '产量'
        else:
            name = '矿主ID: ' + key
        series.append(dict(name=name, yAxis=1, type='column', data=value))

    series.append({'name': '平均速度', 'yAxis': 0, 'type': 'spline', 'data': speed_column_value, 'tooltip': {
        'valueSuffix': ' KB/s'
    }})
    return dict(category=category, series=series)

@app.route('/analyzer/last_30_day')
@requires_auth
def analyzer_last_30_day():
    user = session.get('user_info')
    username = user.get('username')

    value = []
    today = datetime.today()
    for b_data in r_session.mget(
            *['user_data:%s:%s' % (username, (today + timedelta(days=i)).strftime('%Y-%m-%d')) for i in range(-31, 0)]):
        if b_data is None:
            continue
        data = json.loads(b_data.decode('utf-8'))
        update_date = datetime.strptime(data.get('updated_time')[0:10], '%Y-%m-%d')

        value.append([int(time.mktime(update_date.timetuple()) * 1000), data.get('pdc')])

    return Response(json.dumps(dict(value=value)), mimetype='application/json')

@app.route('/analyzer/speed_comparison')
@requires_auth
def analyzer_speed_comparison():
    user = session.get('user_info')
    username = user.get('username')

    str_today = datetime.now().strftime('%Y-%m-%d')
    key = 'user_data:%s:%s:history.speed' % (username, str_today)

    history_speed = dict()
    b_history_speed = r_session.get(key)
    if b_history_speed is None:
        history_speed = __get_history_speed_data(username)
        r_session.setex(key, json.dumps(history_speed), 3600 * 25)
    else:
        history_speed = json.loads(b_history_speed.decode('utf-8'))

    key = 'user_data:%s:%s' % (username, str_today)

    b_today_data = r_session.get(key)
    if b_today_data is None:
        speed_comparison_data = __get_speed_comparison_data(history_speed, [], '2012-10-04 14:39:00')
    else:
        today_data = json.loads(b_today_data.decode('utf-8'))
        speed_comparison_data = __get_speed_comparison_data(history_speed, today_data.get('speed_stat'),
                                                            today_data.get('updated_time'))

    return Response(json.dumps(speed_comparison_data), mimetype='application/json')

@app.route('/analyzer/speed_vs_income')
@requires_auth
def analyzer_speed_vs_income():
    user = session.get('user_info')
    username = user.get('username')

    str_today = datetime.now().strftime('%Y-%m-%d')
    key = 'user_data:%s:%s:%s' % (username, 'speed_vs_income', str_today)

    data = dict()
    b_data = r_session.get(key)
    if b_data is None:
        data = __seven_day_pdc(username)
        r_session.setex(key, json.dumps(data), 3600 * 25)

    else:
        data = json.loads(b_data.decode('utf-8'))

    return Response(json.dumps(data), mimetype='application/json')

@app.route('/analyzer/speed_stat_chart')
@requires_auth
def analyzer_speed_stat_chart():
    user = session.get('user_info')
    username = user.get('username')

    user_key = 'user:%s' % username
    str_today = datetime.now().strftime('%Y-%m-%d')
    key = 'user_data:%s:%s' % (username, str_today)

    b_data = r_session.get(key)
    if b_data is None:
        return Response(json.dumps(dict(value=[], category=[])), mimetype='application/json')

    today_data = json.loads(b_data.decode('utf-8'))

    speed_stat_chart = __get_speed_stat_chart_data(today_data.get('speed_stat'))

    return Response(json.dumps(speed_stat_chart), mimetype='application/json')

@app.route('/analyzer')
@requires_auth
def analyzer():
    return render_template('analyzer.html')
