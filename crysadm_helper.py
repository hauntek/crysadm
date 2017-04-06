__author__ = 'powergx'
import config, socket, redis
import time
from login import login
from datetime import datetime, timedelta
from multiprocessing import Process
from multiprocessing.dummy import Pool as ThreadPool
import threading

conf = None
if socket.gethostname() == 'GXMBP.local':
    conf = config.DevelopmentConfig
elif socket.gethostname() == 'iZ23bo17lpkZ':
    conf = config.ProductionConfig
else:
    conf = config.TestingConfig

redis_conf = conf.REDIS_CONF
pool = redis.ConnectionPool(host=redis_conf.host, port=redis_conf.port, db=redis_conf.db, password=redis_conf.password)
r_session = redis.Redis(connection_pool=pool)

from api import *

# 获取用户数据
def get_data(username):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'get_data')

    start_time = datetime.now()
    try:
        for user_id in r_session.smembers('accounts:%s' % username):

            account_key = 'account:%s:%s' % (username, user_id.decode('utf-8'))
            account_info = json.loads(r_session.get(account_key).decode('utf-8'))

            if not account_info.get('active'): continue

            print("start get_data with userID:", user_id)

            session_id = account_info.get('session_id')
            user_id = account_info.get('user_id')
            cookies = dict(sessionid=session_id, userid=str(user_id))

            mine_info = get_mine_info(cookies)
            time.sleep(3)
            if is_api_error(mine_info):
                print('get_data:', user_id, 'mine_info', 'error')
                return

            if mine_info.get('r') != 0:

                success, account_info = __relogin(account_info.get('account_name'), account_info.get('password'), account_info, account_key)
                if not success:
                    print('get_data:', user_id, 'relogin failed')
                    continue

                session_id = account_info.get('session_id')
                user_id = account_info.get('user_id')
                cookies = dict(sessionid=session_id, userid=str(user_id))
                mine_info = get_mine_info(cookies)

            if mine_info.get('r') != 0:
                print('get_data:', user_id, 'mine_info', 'error')
                continue

            device_info = ubus_cd(session_id, user_id, ["server", "get_devices", {}])
            red_zqb = device_info['result'][1]

            account_data_key = account_key + ':data'
            b_account_data = r_session.get(account_data_key)
            if b_account_data is not None:
                account_data = json.loads(b_account_data.decode('utf-8'))
            else:
                account_data = dict()
                account_data['privilege'] = get_privilege(cookies)

            account_data['updated_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            account_data['mine_info'] = mine_info
            account_data['device_info'] = red_zqb.get('devices')
            account_data['income'] = get_balance_info(cookies)
            account_data['produce_info'] = get_produce_stat(cookies)

            if is_api_error(account_data.get('income')):
                print('get_data:', user_id, 'income', 'error')
                return

            if is_api_error(account_data.get('produce_info')):
                print('get_data:', user_id, 'produce_info', 'error')
                return

            r_session.set(account_data_key, json.dumps(account_data))
            if not r_session.exists('ttl_drawcash'):
                r = get_can_drawcash(cookies)
                if r.get('r') == 0 and r.get('is_tm') == 1:
                    r_session.setex('can_drawcash', '1', 120)
                r_session.setex('ttl_drawcash', '1', 60)

        if start_time.day == datetime.now().day:
            save_history(username)

        r_session.setex('user:%s:cron_queued' % username, '1', 60)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), username.encode('utf-8'), 'successed')

    except Exception as ex:
        print(username.encode('utf-8'), 'failed', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ex)

# 保存历史数据
def save_history(username):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'save_history')

    key = 'user_data:%s:%s' % (username, datetime.now().strftime('%Y-%m-%d'))
    b_today_data = r_session.get(key)
    if b_today_data is not None:
        today_data = json.loads(b_today_data.decode('utf-8'))
    else:
        today_data = dict()

    today_data['updated_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today_data['pdc'] = 0
    today_data['box_pdc'] = 0
    today_data['last_speed'] = 0
    today_data['deploy_speed'] = 0
    today_data['balance'] = 0
    today_data['income'] = 0
    today_data['speed_stat'] = []
    today_data['pdc_detail'] = []
    today_data['produce_stat'] = []

    if today_data.get('refreshes') is None:
        today_data['refreshes'] = 0

    for user_id in r_session.smembers('accounts:%s' % username):
        # 获取账号所有数据
        account_data_key = 'account:%s:%s:data' % (username, user_id.decode('utf-8'))
        b_data = r_session.get(account_data_key)
        if b_data is None:
            continue
        data = json.loads(b_data.decode('utf-8'))

        updated_time = datetime.strptime(data.get('updated_time'), '%Y-%m-%d %H:%M:%S')
        if updated_time + timedelta(minutes=30) < datetime.now() or updated_time.day != datetime.now().day:
            continue

        today_data['refreshes'] += 1

        this_speed = 0
        this_pdc = data.get('mine_info').get('dev_m').get('pdc')

        today_data['pdc'] += this_pdc
        today_data['box_pdc'] += data.get('mine_info').get('td_box_pdc')
        today_data.get('pdc_detail').append(dict(mid=data.get('privilege').get('mid'), pdc=this_pdc))

        today_data['balance'] += data.get('income').get('r_can_use')
        today_data['income'] += data.get('income').get('r_h_a')
        today_data.get('produce_stat').append(dict(mid=data.get('privilege').get('mid'), hourly_list=data.get('produce_info').get('hourly_list')))
        for device in data.get('device_info'):
            this_speed += int(int(device.get('dcdn_upload_speed')) / 1024)
            today_data['last_speed'] += int(int(device.get('dcdn_upload_speed')) / 1024)
            today_data['deploy_speed'] += int(device.get('dcdn_download_speed') / 1024)

        # 新速度统计
        if data.get('zqb_speed_stat') is None:
            data['zqb_speed_stat'] = [0] * 24

        if data.get('zqb_speed_stat_times') is None:
            data['zqb_speed_stat_times'] = 0

        if data.get('zqb_speed_stat_times') == updated_time.hour:
            if data.get('zqb_speed_stat')[23] != 0:
                this_speed = int((this_speed + data.get('zqb_speed_stat')[23] / 8) / 2) # 计算平均值
            data.get('zqb_speed_stat')[23] = this_speed * 8
        else:
            del data['zqb_speed_stat'][0]
            data.get('zqb_speed_stat').append(this_speed * 8)

        data['zqb_speed_stat_times'] = updated_time.hour

        r_session.set(account_data_key, json.dumps(data))
        # 新速度统计

        today_data.get('speed_stat').append(dict(mid=data.get('privilege').get('mid'), dev_speed=data.get('zqb_speed_stat')
                                                if data.get('zqb_speed_stat') is not None else [0] * 24))

    r_session.setex(key, json.dumps(today_data), 3600 * 24 * 35)
    save_income_history(username, today_data.get('pdc_detail'))

# 获取保存的历史数据
def save_income_history(username, pdc_detail):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), username.encode('utf-8'), 'save_income_history')

    now = datetime.now()

    key = 'user_data:%s:%s' % (username, 'income.history')
    b_income_history = r_session.get(key)
    if b_income_history is not None:
        income_history = json.loads(b_income_history.decode('utf-8'))
    else:
        income_history = dict()

    #if now.minute < 50: return

    if income_history.get(now.strftime('%Y-%m-%d')) is None:
        income_history[now.strftime('%Y-%m-%d')] = dict()

    income_history[now.strftime('%Y-%m-%d')][now.strftime('%H')] = pdc_detail

    r_session.setex(key, json.dumps(income_history), 3600 * 72)

# 重新登录
def __relogin(username, password, account_info, account_key):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), username.encode('utf-8'), 'relogin')

    login_result = login(username, password, conf.ENCRYPT_PWD_URL)
    if login_result.get('errorCode') != 0:
        account_info['status'] = login_result.get('errorDesc')
        account_info['active'] = False
        r_session.set(account_key, json.dumps(account_info))
        return False, account_info

    account_info['session_id'] = login_result.get('sessionID')
    account_info['status'] = 'OK'
    r_session.set(account_key, json.dumps(account_info))
    return True, account_info

# 获取在线用户数据
def get_online_user_data():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'get_online_user_data')

    if r_session.exists('api_error_info'): return

    pool = ThreadPool(5)

    pool.map(get_data, (u.decode('utf-8') for u in r_session.smembers('global:online.users')))
    pool.close()
    pool.join()

# 获取离线用户数据
def get_offline_user_data():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'get_offline_user_data')

    if r_session.exists('api_error_info'): return
    #if datetime.now().minute < 50: return
    if not r_session.smembers('users'): return

    offline_users = []
    for b_user in r_session.mget(*['user:%s' % name.decode('utf-8') for name in r_session.sdiff('users', *r_session.smembers('global:online.users'))]):
        user_info = json.loads(b_user.decode('utf-8'))
        if not user_info.get('active'): continue

        username = user_info.get('username')
        if r_session.exists('user:%s:cron_queued' % username): continue
        offline_users.append(username)

    pool = ThreadPool(10)

    pool.map(get_data, offline_users)
    pool.close()
    pool.join()

# 从在线用户列表中清除离线用户
def clear_offline_user():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'clear_offline_user')

    for b_username in r_session.smembers('global:online.users'):
        username = b_username.decode('utf-8')
        if not r_session.exists('user:%s:is_online' % username):
            r_session.srem('global:online.users', username)

# 刷新选择自动任务的用户
def select_auto_task_user():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'select_auto_task_user')

    r_session.delete('global:auto.collect.cookies')
    r_session.delete('global:auto.drawcash.cookies')
    r_session.delete('global:auto.giftbox.cookies')
    r_session.delete('global:auto.shakegift.cookies')
    r_session.delete('global:auto.searcht.cookies')
    r_session.delete('global:auto.revenge.cookies')
    r_session.delete('global:auto.getaward.cookies')

    if not r_session.smembers('users'): return
    for b_user in r_session.mget(*['user:%s' % name.decode('utf-8') for name in r_session.smembers('users')]):
        user_info = json.loads(b_user.decode('utf-8'))
        if not user_info.get('active'): continue

        username = user_info.get('username')
        for user_id in r_session.smembers('accounts:%s' % username):

            account_key = 'account:%s:%s' % (username, user_id.decode('utf-8'))
            account_info = json.loads(r_session.get(account_key).decode('utf-8'))

            if not account_info.get('active'): continue

            session_id = account_info.get('session_id')
            user_id = account_info.get('user_id')
            cookies = json.dumps(dict(sessionid=session_id, userid=str(user_id), user_info=user_info))

            if user_info.get('auto_collect'):
                r_session.sadd('global:auto.collect.cookies', cookies)
            if user_info.get('auto_drawcash'):
                r_session.sadd('global:auto.drawcash.cookies', cookies)
            if user_info.get('auto_giftbox'):
                r_session.sadd('global:auto.giftbox.cookies', cookies)
            if user_info.get('auto_shakegift'):
                r_session.sadd('global:auto.shakegift.cookies', cookies)
            if user_info.get('auto_searcht'):
                r_session.sadd('global:auto.searcht.cookies', cookies)
            if user_info.get('auto_revenge'):
                r_session.sadd('global:auto.revenge.cookies', cookies)
            if user_info.get('auto_getaward'):
                r_session.sadd('global:auto.getaward.cookies', cookies)

# 执行收取水晶函数
def check_collect(cookies):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'check_collect')

    user_info = cookies.get('user_info')
    del cookies['user_info']

    mine_info = get_mine_info(cookies)
    time.sleep(2)
    if mine_info.get('r') != 0: return
    if mine_info.get('td_not_in_a') > 16000:
        r = collect(cookies)
        if r.get('rd') != 'ok':
            log = r.get('rd')
        else:
            log = '收取:%s水晶.' % mine_info.get('td_not_in_a')
        loging(user_info, '自动执行', '收取', cookies.get('userid'), log)
    time.sleep(3)

# 执行自动提现的函数
def check_drawcash(cookies):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'check_drawcash')

    user_info = cookies.get('user_info')
    del cookies['user_info']

    r = get_can_drawcash(cookies)
    time.sleep(2)
    if r.get('r') != 0: return
    if r.get('is_tm') == 0: return
    r = get_balance_info(cookies)
    time.sleep(2)
    if r.get('r') != 0: return
    wc_pkg = r.get('wc_pkg')
    if wc_pkg > 10:
        if wc_pkg > 200: wc_pkg = 200
        r = draw_cash(cookies, wc_pkg)
        loging(user_info, '自动执行', '提现', cookies.get('userid'), r.get('rd'))
    time.sleep(3)

# 执行免费宝箱函数
def check_giftbox(cookies):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'check_giftbox')

    user_info = cookies.get('user_info')
    del cookies['user_info']

    box_info = api_giftbox(cookies)
    time.sleep(2)
    if box_info.get('r') != 0: return
    for box in box_info.get('ci'):
        if box.get('cnum') == 0:
            r = api_openStone(cookies, box.get('id'), '3')
            if r.get('r') != 0:
                log = r.get('rd')
            else:
                log = '开启:获得:%s水晶.' % r.get('get').get('num')
        else:
            r = api_giveUpGift(cookies, box.get('id'))
            if r.get('r') != 0:
                log = r.get('rd')
            else:
                log = '丢弃:收费:%s水晶.' % box.get('cnum')
        loging(user_info, '自动执行', '宝箱', cookies.get('userid'), log)
        break
    time.sleep(3)

# 执行摇晃宝箱函数
def check_shakegift(cookies):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'check_shakegift')

    user_info = cookies.get('user_info')
    del cookies['user_info']

    boxleft = api_shakeLeft(cookies)
    time.sleep(2)
    if boxleft.get('r') != 0: return
    if boxleft.get('left') > 0:
        box_info = api_shakeGift(cookies)
        time.sleep(2)
        if box_info.get('r') != 0: return
        tag = '2' if box_info.get('type') == 1 else '1'
        box = api_stoneInfo(cookies, box_info.get('id'), tag)
        time.sleep(2)
        if box.get('r') != 0: return
        if box.get('cost') == 0:
            r = api_openStone(cookies, box_info.get('id'), 3, tag)
            if r.get('r') != 0:
                log = r.get('rd')
            else:
                log = '开启:获得:%s水晶.' % r.get('get').get('num')
        else:
            r = api_giveUpGift(cookies, box_info.get('id'), tag)
            if r.get('r') != 0:
                log = r.get('rd')
            else:
                log = '丢弃:收费:%s水晶.' % box.get('cost')
        loging(user_info, '自动执行', '宝箱', cookies.get('userid'), log)
    time.sleep(3)

# 执行秘银进攻函数
def check_searcht(cookies):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'check_searcht')

    user_info = cookies.get('user_info')
    del cookies['user_info']

    r = api_sys_getEntry(cookies)
    time.sleep(2)
    if r.get('r') != 0: return
    if r.get('steal_free') > 0:
        steal_info = api_steal_search(cookies)
        time.sleep(2)
        if steal_info.get('r') != 0:
            log = regular_html(steal_info.get('rd'))
        else:
            t = api_steal_collect(cookies, steal_info.get('sid'))
            time.sleep(2)
            if t.get('r') != 0:
                log = 'Forbidden'
            else:
                log = '获得:%s秘银.' % t.get('s')
                api_steal_summary(cookies, steal_info.get('sid'))
        loging(user_info, '自动执行', '进攻', cookies.get('userid'), log)
    time.sleep(3)

# 执行秘银复仇函数
def check_revenge(cookies):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'check_revenge')

    user_info = cookies.get('user_info')
    del cookies['user_info']

    r = api_steal_stolenSilverHistory(cookies)
    time.sleep(2)
    if r.get('r') != 0: return
    for steal in r.get('list'):
        if steal.get('st') != 0: continue
        steal_info = api_steal_search(cookies, steal.get('sid'))
        time.sleep(2)
        if steal_info.get('r') != 0:
            log = regular_html(steal_info.get('rd'))
        else:
            t = api_steal_collect(cookies, steal_info.get('sid'))
            time.sleep(2)
            if t.get('r') != 0:
                log = 'Forbidden'
            else:
                log = '获得:%s秘银.' % t.get('s')
                api_steal_summary(cookies, steal_info.get('sid'))
        loging(user_info, '自动执行', '复仇', cookies.get('userid'), log)
        break
    time.sleep(3)

# 执行幸运转盘函数
def check_getaward(cookies):
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'check_getaward')

    user_info = cookies.get('user_info')
    del cookies['user_info']

    mine_info = get_mine_info(cookies)
    time.sleep(2)
    if mine_info.get('r') != 0: return
    if mine_info.get('s') > 5000:
        r = api_getconfig(cookies)
        time.sleep(2)
        if r.get('rd') != 'ok': return
        if r.get('cost') > 5000: return
        r = api_getaward(cookies)
        if r.get('rd') != 'ok':
            log = r.get('rd')
        else:
            log = '获得:%s' % regular_html(r.get('tip'))
        loging(user_info, '自动执行', '转盘', cookies.get('userid'), log)
    time.sleep(3)

# 收取水晶
def collect_crystal():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'collect_crystal')

    for cookie in r_session.smembers('global:auto.collect.cookies'):
        check_collect(json.loads(cookie.decode('utf-8')))

# 自动提现
def drawcash_crystal():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'drawcash_crystal')

    if not r_session.exists('can_drawcash'): return

    for cookie in r_session.smembers('global:auto.drawcash.cookies'):
        check_drawcash(json.loads(cookie.decode('utf-8')))

# 免费宝箱
def giftbox_crystal():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'giftbox_crystal')

    for cookie in r_session.smembers('global:auto.giftbox.cookies'):
        check_giftbox(json.loads(cookie.decode('utf-8')))

# 摇晃宝箱
def shakegift_crystal():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'shakegift_crystal')

    for cookie in r_session.smembers('global:auto.shakegift.cookies'):
        check_shakegift(json.loads(cookie.decode('utf-8')))

# 秘银进攻
def searcht_crystal():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'searcht_crystal')

    for cookie in r_session.smembers('global:auto.searcht.cookies'):
        check_searcht(json.loads(cookie.decode('utf-8')))

# 秘银复仇
def revenge_crystal():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'revenge_crystal')

    for cookie in r_session.smembers('global:auto.revenge.cookies'):
        check_revenge(json.loads(cookie.decode('utf-8')))

# 幸运转盘
def getaward_crystal():
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'getaward_crystal')

    for cookie in r_session.smembers('global:auto.getaward.cookies'):
        check_getaward(json.loads(cookie.decode('utf-8')))

# 正则过滤 + URL转码
def regular_html(info):
    import re
    from urllib.parse import unquote
    regular = re.compile('<[^>]+>')
    url = unquote(info)
    return regular.sub("", url)

# 自动日记记录
def loging(user, clas, types, userid, gets):

    key = 'record:%s:%s' % (user.get('username'), datetime.now().strftime('%Y-%m-%d'))
    b_today_data = r_session.get(key)
    if b_today_data is not None:
        today_data = json.loads(b_today_data.decode('utf-8'))
    else:
        today_data = dict()
        today_data['diary'] = []

    log_as_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    body = dict(clas=clas, type=types, id=userid, gets=gets, time=log_as_time)

    today_data.get('diary').append(body)

    r_session.setex(key, json.dumps(today_data), 3600 * 24 * 15)

# 计时器函数，定期执行某个线程，时间单位为秒
def timer(func, seconds):
    while True:
        pro = Process(target=func)
        pro.start()
        pro.join() # 等待上个进程完成

        time.sleep(seconds)

if __name__ == '__main__':
    # 执行收取水晶时间，单位为秒，默认为30秒。
    # 每30分钟检测一次收取水晶
    threading.Thread(target=timer, args=(collect_crystal, 60*30)).start()
    # 执行自动提现时间，单位为秒，默认为60秒。
    # 每60分钟检测一次自动提现
    threading.Thread(target=timer, args=(drawcash_crystal, 60*60)).start()
    # 执行免费宝箱时间，单位为秒，默认为40秒。
    # 每40分钟检测一次免费宝箱
    threading.Thread(target=timer, args=(giftbox_crystal, 60*40)).start()
    # 执行摇晃宝箱时间，单位为秒，默认为50秒。
    # 每50分钟检测一次摇晃宝箱
    threading.Thread(target=timer, args=(shakegift_crystal, 60*50)).start()
    # 执行秘银进攻时间，单位为秒，默认为180秒。
    # 每180分钟检测一次秘银进攻
    threading.Thread(target=timer, args=(searcht_crystal, 60*60*3)).start()
    # 执行秘银复仇时间，单位为秒，默认为240秒。
    # 每240分钟检测一次秘银复仇
    threading.Thread(target=timer, args=(revenge_crystal, 60*60*4)).start()
    # 执行幸运转盘时间，单位为秒，默认为300秒。
    # 每300分钟检测一次幸运转盘
    threading.Thread(target=timer, args=(getaward_crystal, 60*60*5)).start()
    # 刷新在线用户数据，单位为秒，默认为30秒。
    # 每30秒刷新一次在线用户数据
    threading.Thread(target=timer, args=(get_online_user_data, 30)).start()
    # 刷新离线用户数据，单位为秒，默认为90秒。
    # 每90秒刷新一次离线用户数据
    threading.Thread(target=timer, args=(get_offline_user_data, 90)).start()
    # 从在线用户列表中清除离线用户，单位为秒，默认为60秒。
    # 每60秒检测一次用户是否在线
    threading.Thread(target=timer, args=(clear_offline_user, 60)).start()
    # 刷新选择自动任务的用户，单位为秒，默认为10分钟
    threading.Thread(target=timer, args=(select_auto_task_user, 60*10)).start()
    while True:
        time.sleep(1)
