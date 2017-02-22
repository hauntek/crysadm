__author__ = 'azjcode'
from flask import request, Response, session, render_template, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import os
import os.path
import json
import hashlib
import urllib.request
import shutil
import threading

service_url = 'http://down.crysadmapp.cn/crysadm'
# service_url = 'https://github.com/hauntek/crysadm/raw/master/'
rootdir = './' # 脚本当前路径
ignore_file = ['config.py'] # 忽略文件

progress = 0

def urlopen(url):
    return urllib.request.urlopen(url).readlines()

def urlretrieve(url, filename):
    urllib.request.urlretrieve(url, filename) 

def SnapshotW(path, cont):
    f = open(path, "a")
    for con in cont:
        j_con = json.dumps(con)
        r = f.write(j_con + "\n") 
    f.close()
    return r

def md5Checksum(filePath):
    fh = open(filePath, 'rb')
    m = hashlib.md5()
    while True:
        data = fh.read(8192)
        if not data:
            break
        m.update(data)
    fh.close()
    return m.hexdigest()

# 检查目录及子目录文件，生成md5校验
def Checksum(rootdir='./', check=False):
    data_list = list()
    for parent, dirnames, filenames in os.walk(rootdir):
        for filename in filenames:
            file = os.path.join(parent, filename)
            file = file.replace('\\', '/') # 路径转换
            file = file.replace(rootdir, '') # 根目录转换

            try:
                md5 = md5Checksum(file)
            except Exception as e:
                continue

            payload = {
                'file': file,
                'md5': md5,
            }
            data_list.append(payload)

    if check == True:
        if os.path.exists('filemd5.txt'):
            os.remove('filemd5.txt') # 删除本地校验记录
        if len(data_list) > 0:
            SnapshotW('filemd5.txt', data_list) # 生成本地校验记录

    return data_list

def down_thread(url, data_list):
    global progress
    progress = 0
    number = 0
    try:
        for data in data_list:
            urls = url + data.get('file')
            filename = data.get('file')
            fname = filename.split('/')[-1]
            if fname != filename:
                dirpath = filename.replace(fname, '/' + fname)
                dirpath = dirpath.split('//')[0]
                if not os.path.exists(dirpath):
                    os.makedirs(dirpath)
            urlretrieve(urls, filename)
            number += 1
            progress = number / len(data_list) * 100 # 百分比进度算法
    except Exception as e:
        pass

    print('下载完成')

# 反馈百分比进度
@app.route('/admin/update/progress', methods=['POST'])
@requires_admin
def update_progress():
    progres = progress
    if progres == 0: progres = 72
    progres = '%.2f' % progres
    return json.dumps(dict(result=progres))

# 检查项目
@app.route('/admin/insp_update', methods=['POST'])
@requires_admin
def insp_update():

    data_list = list()
    data_file = Checksum(rootdir, False) # 是否生成本地校验记录

    try:
        data = urlopen(service_url + '/filemd5.txt')
        for b_date in data:
            data_info = json.loads(b_date.decode('utf-8'))
            if data_info['file'] in ignore_file: continue
            if data_info in data_file: continue
            data_list.append(data_info)
            # print(data_info)
    except Exception as e:
        return json.dumps(dict(r='', msg='云端对比文件出现错误，请稍后重试'))

    return json.dumps(dict(r='ok', list=data_list))

# 更新项目
@app.route('/admin/update', methods=['POST'])
@requires_admin
def update(backups=True):

    if progress > 0 and progress < 100:
        return json.dumps(dict(r='', msg='正在更新中...'))

    if app.debug == True:
        return json.dumps(dict(r='', msg='在线更新不建议在调试模式下进行，请修改config.py ProductionConfig类 DEBUG = False<br />ps:你也可以用命令方式更新 直接运行update_flash.py即可'))

    data_list = list()
    data_file = Checksum(rootdir, True) # 是否生成本地校验记录

    try:
        data = urlopen(service_url + '/filemd5.txt')
        for b_date in data:
            data_info = json.loads(b_date.decode('utf-8'))
            if data_info['file'] in ignore_file: continue
            if data_info in data_file: continue
            data_list.append(data_info)
            # print(data_info)
    except Exception as e:
        return json.dumps(dict(r='', msg='云端对比文件出现错误，请稍后重试'))

    url = service_url + '/'
    if len(data_list) > 0:
        if backups:
            if os.path.exists('.backups'):
                shutil.rmtree('.backups')
            shutil.copytree('.', '.backups')
        threading.Thread(target=down_thread, args=(url, data_list)).start()
    else:
        return json.dumps(dict(r='', msg='本地源代码和云端一致，无需更新'))

    return json.dumps(dict(r='ok', msg=''))
