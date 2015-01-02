# -*- coding: utf-8 -*-

import os
import sys
import re
from copy import copy
from functools import wraps
import errno
import signal
import email

class TimeoutError(Exception):
    pass

def is_exe_file(path):
    path = os.path.realpath(path)
    return os.path.isfile(path) and os.access(path, os.X_OK)

def get_prefix():
    for attr in ('real_prefix', 'prefix'):
        prefix = getattr(sys, attr, None)
        if prefix is not None:
            return prefix
    else:
        raise EnvironmentError('could not determine your prefix.')

def get_real_python_exe():
    prefix = get_prefix()
    for root, dirs, files in os.walk(prefix):
        for file in files:
            if file == 'python':
                path = os.path.join(root, file)
                if is_exe_file(path):
                    return path
    raise EnvironmentError('Could not find real python interpreter.')

class ItemAttrDict(dict):

    def __init__(self, *args, **kwargs):
        super(ItemAttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self

def get_stdlib_dirs():
    paths = []
    prefix = get_prefix()
    for path in [prefix]:
        for root, dirs, files in os.walk(path):
            if '__future__.py' in files:  # FIXME
                paths.append(root)
            if 'time.so' in files:
                paths.append(root)
    if not paths:
        raise EnvironmentError('Could not find stdlib dirs.')
    paths = set([os.path.realpath(f) for f in paths])
    return list(paths)


# stolen from: https://github.com/joeyespo/py-getch
try:
    from msvcrt import getch
except ImportError:
    def getch():
        import tty
        import termios
        stdin_fd = sys.stdin.fileno()
        old = termios.tcgetattr(stdin_fd)
        try:
            tty.setraw(stdin_fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old)

def extract_base_module_name(statement):
    import_re = '^(import|from)\s+(?P<modname>[^\.\s]*)($|\..*|\s.*)'
    match = re.match(import_re, statement)
    if match is not None:
        return match.group('modname')
    else:
        return None

def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result
        return wraps(func)(wrapper)
    return decorator

def smart_name_addr_split(text):
    text = text.strip('\t;, ')
    if not text:
        return text
    info = []
    text = re.split(r'[,;]', text)
    for item in text:
        name, mail = email.utils.parseaddr(item)
        info.append((name, mail))
    return info


def get_real_python_dir(type='prefix'):
    base = get_prefix()
    if type == 'prefix':
        path = base
    elif type == 'bin':
        path = os.path.join(base, 'bin')
    elif type == 'stdlib':
        path = os.path.join(base, 'lib', 'python2.7')
    else:
        raise ValueError('{0}: unknown python path type'.format(type))
    return path

