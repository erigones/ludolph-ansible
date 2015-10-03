#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Ludolph: Ansible plugin
# Copyright (C) 2015 Erigones, s. r. o.
#
# See the LICENSE file for copying permission.

import codecs
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

# noinspection PyPep8Naming
from ludolph_ansible import __version__ as VERSION

DESCRIPTION = 'Ludolph: Ansible plugin'

with codecs.open('README.rst', 'r', encoding='UTF-8') as readme:
    LONG_DESCRIPTION = ''.join(readme)

DEPS = ['ludolph>=0.7.0', 'ansible']

CLASSIFIERS = [
    'Environment :: Console',
    'Environment :: Plugins',
    'Intended Audience :: Developers',
    'Intended Audience :: Education',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: MIT License',
    'Operating System :: MacOS',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 3',
    'Topic :: Communications :: Chat',
    'Topic :: Utilities'
]

packages = [
    'ludolph_ansible',
]

setup(
    name='ludolph-ansible',
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author='Erigones',
    author_email='erigones [at] erigones.com',
    url='https://github.com/erigones/ludolph-ansible/',
    license='MIT',
    packages=packages,
    install_requires=DEPS,
    platforms='any',
    classifiers=CLASSIFIERS,
    include_package_data=True
)
