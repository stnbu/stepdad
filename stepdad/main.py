# -*- coding: utf-8 -*-

import sys
import os
import sys
import time
import collections
import distutils
import imp
import re
import email.utils
import shutil
import subprocess
import tempfile
import tokenize
from pprint import pformat
from copy import copy
from glob import glob
from tempfile import NamedTemporaryFile
import modulefinder
from utils import *
import logging


url_regex = {
    'pypi_project': r'\s*https?://pypi.python.org/pypi/(?P<pypi_project>[^/\s]+)/?',
    'github_repository': r'\s*https?://github.com/(?P<github_user>[^/]+)/(?P<github_repository>[^/]+)[/]?.*',
    'sf_project_hosted': r'\s*https?://(?P<sf_project>[^\.]+).sourceforge.net/.*',
    'sf_project': r'\s*https?://sourceforge.net/p(?:rojects)?/(?P<sf_project>[^/]+)[/]?.*',
    'osi_license_name': r'\s*https?://(?:[w]+\.)?opensource.org/licenses/(?P<license_name>\w+)(?:\.html)?.*',
}

__all__ = []

url_cre = [(k, re.compile(s)) for k,s in url_regex.iteritems()]
url_cre = dict(url_cre)

def get_wellknown_url_data(text):
    url_data = {}
    for key, cre in url_cre.iteritems():
        for match in cre.finditer(text, re.MULTILINE):
            if match is not None:
                url_data.update(match.groupdict())
    return url_data

UTIL_NAME = 'dumbmodule'
UTIL_URL = 'https://github.com/stnbu/{0}'.format(UTIL_NAME)
THIS_DIR = os.path.dirname(__file__)
THIS_DIR = os.path.abspath(THIS_DIR)
IMPORT_TEST_WRAPPER_PATH = os.path.join(THIS_DIR, 'import_test_wrapper.py')
SETUP_TEMPLATE = os.path.join(THIS_DIR, 'data', 'setup.py.template')

def guess_cli_func_name(path):
    Token = collections.namedtuple('Token', ['type', 'str', 'begin', 'end', 'line'], verbose=False)
    past_main_stanza = False
    last_token = None
    func_names = []
    g = tokenize.generate_tokens(open(path, 'r').readline)
    for token_args in g:
        token = Token(*token_args)

        if last_token is not None and last_token.str == 'def':
            func_names.append(token.str)
        else:
            pass

        if (last_token is not None and
            last_token.type is tokenize.NAME and last_token.str == 'if'
            and token.type is tokenize.NAME and token.str == '__name__'):
            for type, name in [(tokenize.OP, '=='), (tokenize.STRING, '__main__'), (tokenize.OP, ':')]:
                main_stanza_token = Token(*g.next())
                if type is tokenize.STRING and name and name[0] in ('"', "'"):
                    name = eval(name)
                if main_stanza_token.type is tokenize.STRING and main_stanza_token.str and main_stanza_token.str[0] in ('"', "'"):
                    s = eval('str({0})'.format(main_stanza_token.str))
                    main_stanza_token = main_stanza_token._replace(str=s)
                if main_stanza_token.type is not type or main_stanza_token.str != name:
                    return None  # FIXME
            past_main_stanza = True
        elif past_main_stanza:
            if token.type is tokenize.OP and token.str == '(':
                if last_token.type is tokenize.NAME and last_token.str in func_names:
                    return last_token.str
        last_token = token


class StaticAnalysis(object):

    known_license_patterns = [
        'BSD',
        'MIT',
        'MPL',
        'ZPL',
        '[L]?GPL(v\d+\+)?',
        'Apache Software License',
        'GNU General Public License',
        'Mozilla Public License',
        'Zope Public License',
    ]

    lic_re=r'|'.join(known_license_patterns)
    lic_re = re.sub(r'\s+', '\s+', lic_re)

    def __init__(self, text):
        self.text = text
        self._attrs = None

    @property
    def attrs(self):
        if self._attrs is not None:
            return self._attrs

        self._attrs = ItemAttrDict()
        reges = [
            (r'.*(?P<license>{0}).*'.format(self.lic_re), 0),
            (r'^[\s#]*(?::license:\s+)(?P<license>{0})'.format(self.lic_re), 0),
            (r'[\s#]*(?::copyright:|Copyright|\(C\))\s+\s*(?:\(C\))\s+(?P<copyright_years>\d+(?:-\d+)?)\s*(?:by\s+)?(?P<copyright_names>.*)', re.IGNORECASE),
            (r'^\s*[:]?(:?[aA]uthor:\s+)(?P<author>.*)$', re.IGNORECASE),
        ]

        for line in self.text.splitlines():
            for reg, flags in reges:
                match = re.match(reg, line, flags)
                if match is not None:
                    self._attrs.update(match.groupdict())


        def use_preferred_alias(string):
            aliases = [
                ('GNU General Public License', 'GPL'),
            ]
            for text, alias in aliases:
                string = string.replace(text, alias)
            return string

        self._attrs = ItemAttrDict([(n,use_preferred_alias(v)) for n,v in self._attrs.iteritems()])

        for name_info in [self._attrs.get('author', ''), self._attrs.get('copyright_names', '')]:
            info = smart_name_addr_split(name_info)
            if not info:
                continue
            info = list(set(info))
            if len(info) > 1:
                info = info[0:1]
            info, = info   # FIXME
            if all([not s.strip() for s in info]):
                continue
            if len(info) > 2:
                info = info[0:2]
            author, mail = info
            if mail and author:
                self._attrs.author_email = mail
                self._attrs.author = author

        return self._attrs

    def get_urls(self):
        url_re = r'https?://\S+'
        return set(re.findall(url_re, self.text, re.MULTILINE | re.IGNORECASE))

class DumbSetup(object):

    package_name_cre = re.compile(r'^[a-zA-Z]\w*$')

    def __init__(self,
                 module_path,
                 root_path,
                 guess=True,
                 interactive=False,
                 import_analysis=True,
                 static_analysis=True,
                 jailed_exec_analysis=True,
                 python_tokenizer_analysis=True,):

        self.guess = guess  # Try and pull things out of module.py automatically (vers, etc.)
        self.interactive = interactive
        self.import_analysis = import_analysis
        self.static_analysis = static_analysis
        self.jailed_exec_analysis = jailed_exec_analysis
        self.python_tokenizer_analysis = python_tokenizer_analysis
        self.module_path = module_path
        self.module_path = os.path.abspath(self.module_path)
        self.module_text = open(self.module_path, 'r').read()
        self.name = os.path.basename(self.module_path)
        self.name, self.ext= os.path.splitext(self.name)
        self.module = None
        self.urls = set()
        self.url_data = ItemAttrDict()
        url_data = get_wellknown_url_data(self.module_text)
        self.url_data.update(url_data)
        self.static_doc = StaticAnalysis(text=self.module_text)
        urls = self.static_doc.get_urls()
        self.urls.update(urls)
        if self.import_analysis:
            self.module = self.get_module()
        if self.ext not in ('.py', '.py3'):
            raise ValueError('{0}: File must be a python module ending in a valid file extension.'.format(self.module_path))
        if not self.acceptable_name(self.name):
            raise ValueError('Name "{0}" does not match requirement pattern "{1}"'.format(self.name, self.package_name_cre.pattern))
        self._kwargs = None
        self.timestamp = int(time.time())
        self.root_path = root_path
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)
        else:
            files = glob(os.path.join(self.root_path, '*'))
            for file in files:
                os.unlink(file)

    @timeout(2)
    def get_module(self):
        so, se = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = open(os.devnull, 'w')
        module = None
        try:
            module = imp.load_source('_{0}'.format(self.name), self.module_path)
        except (SyntaxError, ImportError, ValueError) as e:
            pass
        except SystemExit:
            pass
        except Exception as e:
            pass
        finally:
            sys.stdout, sys.stderr = so, se
        return module

    @property
    def kwargs_defaults(self):
        defaults = ItemAttrDict()
        defaults.name = self.name
        defaults.version = '.'.join(['0', '0', str(self.timestamp)])
        defaults.description = 'Auto-packaged module "{0}". See long description for details.'.format(self.name)
        ld = ('"{name}" is a singleton python module that lacked any existing pip/distutils '
              'framework. It has been packaged by the "{util_name}" auto-packaging utility. '
              'Please see `the {name} site <{util_url}>`_ for more information.' )
        ld = ld.format(util_name=UTIL_NAME, util_url=UTIL_URL, **defaults)
        defaults.long_description = ld
        defaults.author = None
        defaults.author_email = None
        defaults.url = None
        defaults.license = None
        defaults.entry_points = {}
        defaults.classifiers = ['Development Status :: 2 - Pre-Alpha']
        defaults.py_modules = [self.name]
        defaults.zip_safe = False
        return defaults

    def get_guesses(self):

        kwargs = ItemAttrDict()

        if self.import_analysis and self.module is not None:
            cre_template = '^[_]*{0}'
            self.kwarg_re_mapping = [
                # kwarg     # compiled regex
                ('version',  cre_template.format('vers') + '|VERSION|version'),
                ('author',  cre_template.format('author')),
                ('author_email',  '^[_]*[e]*mail'),
                ('url',  cre_template.format('url')),
                ('license',  cre_template.format('license')),
                ('description',  cre_template.format('desc')),
            ]
            self.kwarg_re_mapping = [(n, re.compile(v)) for n,v in self.kwarg_re_mapping]
            for name, cre in self.kwarg_re_mapping:
                candidates = [(n,v) for n,v in self.module.__dict__.iteritems() if cre.match(n)]
                if candidates:
                    candidate = sorted(candidates)[-1]
                    if candidate:
                        value = candidate[1]
                        if not isinstance(value, basestring):
                            continue
                        kwargs[name] = value
            if self.module.__doc__ and len(self.module.__doc__) > 5:
                kwargs.long_description = self.module.__doc__

        if self.python_tokenizer_analysis:
            func_name = guess_cli_func_name(self.module_path)
            if func_name is not None:
                entry_points = {
                    'console_scripts': [
                        '{module_name} = {module_name}:{func_name}'.format(module_name=self.name, func_name=func_name),
                    ],
                }
            else:
                entry_points = {}
            kwargs.entry_points = entry_points

        if self.static_analysis:
            self.static_doc = StaticAnalysis(text=self.module_text)
            if self.static_doc.attrs:
                kwargs.update(self.static_doc.attrs)
            if len(self.urls) == 1:
                kwargs.url, = self.urls

        pre_exec_state = {
            'globals()': copy(globals()),
            'os.environ': copy(os.environ),
            'sys.modules': copy(sys.modules),
            'sys.path': copy(copy(sys.path))
        }

        self.missing_modules = []
        if self.jailed_exec_analysis:
            try:
                REASONABLE_PATH = '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
                os.environ['PATH'] = get_real_python_dir('bin') + ':' + REASONABLE_PATH

                mf = modulefinder.ModuleFinder()
                sys.path[0:] = get_stdlib_dirs()
                mf.load_file(self.module_path)
                self.missing_modules = mf.any_missing()
            finally:
                globals().update(pre_exec_state['globals()'])

            kwargs.requires = self.missing_modules

        return kwargs

    def get_setup_text(self):
        #pre_exec_state['sys.path']
        setup = open(SETUP_TEMPLATE, 'r').read()
        setup = setup.format(kwargs=pformat(self.kwargs))
        return setup

    def write_setup_py(self):
        path = os.path.join(self.root_path, 'setup{0}'.format(self.ext))
        with open(path, 'w') as f:
            text = self.get_setup_text()
            f.write(text)

    @property
    def kwargs(self):
        if self._kwargs is not None:
            return self._kwargs
        self._kwargs = ItemAttrDict()
        self._kwargs.update(self.kwargs_defaults)  # load the defaults

        if self.guess:
            guesses = self.get_guesses()
            self._kwargs.update(guesses)

        if self.interactive:
            edit_setup_file = NamedTemporaryFile(suffix='.py')
            header = ('# -*- coding: utf-8 -*-\n'
                      '\n'
                      '# Make any necessary changes to the data below. Results\n'
                      '# must be valid Python. If syntax errors are detected, you\n'
                      '# will have an opportunity to re-edit.\n'
                      '\n'
                      )
            edit_setup_file.write(header)
            edit_setup_file.write('kwargs = ')
            edit_setup_file.write(pformat(self._kwargs))
            edit_setup_file.write('\n')
            edit_setup_file.write('\n')
            edit_setup_file.flush()
            editors = [os.getenv('EDITOR'), 'editor', 'vim', 'emacs', 'vi', 'nano', 'ed']
            for name in editors:
                editor = distutils.spawn.find_executable(name)
                if editor is not None:
                    break
            else:
                raise RuntimeError('Found no editor. Tried: {0}'.format(', '.join(editors)))
            retval = None
            while True:
                retval = subprocess.call([editor, edit_setup_file.name])
                try:
                    kwargs = imp.load_source('_edit_setup_file', edit_setup_file.name).kwargs
                    self._kwargs.update(kwargs)
                    break
                except SyntaxError as e:
                    message = ('==============================\n'
                               'Error: {msg} near line {lineno}, column {offset}:\n'
                               '\n'
                               '{text}'
                               '\n'
                               'Press "q" to give up, any other key to edit again.\n'
                                '==============================\n'
                               )
                    message = message.format(msg=e.msg, lineno=e.lineno, offset=e.offset, text=e.text)
                    print >>sys.stderr, message
                    ch = getch().lower()
                    if ch in ('q',):
                        break

        for name_info in [self._kwargs.get('author', None)]:
            if name_info is None:
                continue
            info = smart_name_addr_split(name_info)
            #info = list(set(info))
            if len(info) > 1:
                info = info[0:1]
            info, = info   # FIXME
            if all([not s.strip() for s in info]):
                continue
            if len(info) > 2:
                info = info[0:2]
            author, mail = info
            if mail and author:
                self._kwargs.author_email = mail
                self._kwargs.author = author

        kwargs = [(n,v) for n,v in self._kwargs.iteritems() if
                  (v is not None and
                  v != [] and
                  v != {} and
                  v != () and
                  v != set())]
        self._kwargs = ItemAttrDict(kwargs)
        self._kwargs.pop('copyright_names', None)
        self._kwargs.pop('copyright_years', None)
        return self._kwargs

    def acceptable_name(self, name):
        return bool(self.package_name_cre.match(name))

    def install_module_to_root_dir(self):
        dest = os.path.join(self.root_path, '{0}{1}'.format(self.name, self.ext))
        shutil.copyfile(self.module_path, dest)
