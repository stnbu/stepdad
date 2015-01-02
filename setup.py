# -*- coding: utf-8 -*-

from setuptools import setup
import stepdad
NAME = 'stepdad'

# README.rst dynamically generated:
with open('README.rst', 'w') as f:
    f.write(stepdad.__doc__)

def read(file):
    with open(file, 'r') as f:
        return f.read().strip()

setup(
    name=NAME,
    version=read('VERSION'),
    description='Automatically package those singleton modules that keep getting lost. Other organziational benifits.',
    long_description=read('README.rst'),
    author='Mike Burr',
    author_email='mburr@unintuitive.org',
    url='https://github.com/stnbu/{0}'.format(NAME),
    download_url='https://github.com/stnbu/{0}/archive/master.zip'.format(NAME),
    provides=[NAME],
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',

    ],
    test_suite='test',
    packages=[NAME],
    keywords=['pip', 'package managementt',],
    entry_points={
        'console_scripts': [ '{0} = {0}.run:main'.format(NAME),],
    },
)
