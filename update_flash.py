__author__ = 'azjcode'
import os
import os.path
import json
import hashlib
import urllib.request
import shutil
import threading

# PS:本脚本直接运行，即可下载全部文件（会覆盖全部，运行前建议备份原文件）

service_url = 'http://down.crysadmapp.cn/crysadm'
# service_url = 'https://github.com/hauntek/crysadm/raw/master/'
rootdir = '.' # 脚本当前路径
ignore_path = ['.backups'] # 忽略目录
ignore_file = [] # 忽略文件

if os.path.exists('filemd5.txt'):
    os.remove('filemd5.txt') # 删除本地校验记录

def urlopen(url):
    return urllib.request.urlopen(url).readlines()

def urlretrieve(url, filename):
    urllib.request.urlretrieve(url, filename) 

def Snapshot(path):
    f = open(path, "r")
    car = f.read()
    f.close()
    return car

def SnapshotW(path, cont):
    f = open(path, "a")
    for con in cont:
        r = f.write(con + "\n") 
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
def Checksum(rootdir='.', check=False):
    data_list = list()
    for parent, dirnames, filenames in os.walk(rootdir):
        path = parent.replace('\\', '/') # 路径转换
        path = path.replace(rootdir + '/', '') # 根目录转换
        if path in ignore_path: continue

        for filename in filenames:
            file = os.path.join(parent, filename)
            md5 = md5Checksum(file)
            file = file.replace('\\', '/') # 路径转换
            file = file.replace(rootdir + '/', '') # 根目录转换
            payload = json.dumps({
                "file": file,
                "md5": md5,
            })
            data_list.append(payload)

    if check == True:
        if len(data_list) > 0:
            SnapshotW('filemd5.txt', data_list) # 生成本地校验记录

    return data_list

def down_thread(url, data_list):
    try:
        for data in data_list:
            urls = url + data.get('file')
            filename = data.get('file')
            # print(filename)
            fname = filename.split('/')[-1]
            dirpath = filename.replace(fname, '/' + fname)
            dirpath = dirpath.split('//')[0]
            if not os.path.exists(dirpath):
                if fname != filename:
                    os.makedirs(dirpath)
            urlretrieve(urls, filename)
    except Exception as e:
        pass

    print('下载完成')

def insp_update():

    data_list = list()
    data_file = ''
    Checksum(rootdir, True) # 是否校验，不校验话直接下载云端全部文件

    if os.path.exists('filemd5.txt'):
        data_file = Snapshot('filemd5.txt') # 取本地校验记录

    try:
        data = urlopen(service_url + '/filemd5.txt')
        for b_date in data:
            data_info = json.loads(b_date.decode('utf-8'))
            if data_info['file'] in ignore_file: continue
            if data_info['md5'] in data_file: continue
            data_list.append(data_info)
            print('发现更新文件：' % data_info['file'])
    except Exception as e:
        return '云端对比文件出现错误，请稍后重试'

    return json.dumps(dict(result=data_list))

def update(backups=True):

    data_list = list()
    data_file = ''
    Checksum(rootdir, True) # 是否校验，不校验话直接下载云端全部文件

    if os.path.exists('filemd5.txt'):
        data_file = Snapshot('filemd5.txt') # 取本地校验记录

    try:
        data = urlopen(service_url + '/filemd5.txt')
        for b_date in data:
            data_info = json.loads(b_date.decode('utf-8'))
            if data_info['file'] in ignore_file: continue
            if data_info['md5'] in data_file: continue
            data_list.append(data_info)
            print('发现更新文件：%s' % data_info['file'])
    except Exception as e:
        return '云端对比文件出现错误，请稍后重试'

    url = service_url + '/'
    if len(data_list) > 0:
        if backups:
            if os.path.exists('.backups'):
                shutil.rmtree('.backups')
            shutil.copytree('.', '.backups')
        threading.Thread(target=down_thread, args=(url, data_list)).start()
    else:
        return '本地源代码和云端一致，无需更新'

    return ''

print(update(False))
