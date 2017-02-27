__author__ = 'azjcode'
from flask import request, Response, session, render_template, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import sys
import os
import json
import subprocess
import tempfile

EXEC = sys.executable
TEMP = tempfile.mkdtemp()
INDEX = 0

def get_name():
    global INDEX
    INDEX = INDEX + 1
    return 'test_%d' % INDEX

def write_py(name, code):
    fpath = os.path.join(TEMP, '%s.py' % name)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(code)
    return fpath

def decode(s):
    try:
        return s.decode('utf-8')
    except UnicodeDecodeError:
        return s.decode('gbk')

# 显示终端页面
@app.route('/admin/console')
@requires_admin
def console():
    return render_template('console.html')

# 执行CODE文件
@app.route('/admin/console/run', methods=['POST'])
@requires_admin
def console_run():

    if request.values.get('code') is None:
        return json.dumps(dict(r='', msg='invalid_params'))

    if request.values.get('code').strip() == '':
        return json.dumps(dict(r='', msg='空'))

    name = get_name()
    code = request.values.get('code')

    try:
        fpath = write_py(name, code)
        output = decode(subprocess.check_output([EXEC, fpath], stderr=subprocess.STDOUT, timeout=5))
        return json.dumps(dict(r='ok', output=output))
    except subprocess.CalledProcessError as e:
        return json.dumps(dict(r='', msg=decode(e.output)))
    except subprocess.TimeoutExpired as e:
        return json.dumps(dict(r='', msg='执行超时'))
    except subprocess.CalledProcessError as e:
        return json.dumps(dict(r='', msg='执行错误'))

    return json.dumps(dict(r='', output=''))
