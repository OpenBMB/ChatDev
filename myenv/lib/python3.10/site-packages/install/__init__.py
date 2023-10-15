#!/usr/bin/python
__version__ = "1.3.5"

import subprocess
import sys
import os
import tempfile
import importlib

if sys.version[0] == '3':
    import urllib.request as url
    from shlex import quote
else:
    import urllib as url
    from pipes import quote

def _get_pip():
    fd, path = tempfile.mkstemp('_get-pip.py')
    url.urlretrieve("https://bootstrap.pypa.io/get-pip.py", path)
    subprocess.check_call([sys.executable, path])

def _check_pip():
    try:
        with open(os.devnull, 'w') as DEVNULL:
            subprocess.check_call([sys.executable, '-m', 'pip'], stdout=DEVNULL)
        return True
    except subprocess.CalledProcessError as exc:
        return False

def install(pkg, use_pep517=None, requirements=None, pip_options=None, install_options=None):
    """Install packages dynamically in your code

    Args:
        pkg: Name of the package or requirements.txt file as a string, you can also use version specifiers like requests==1.2.3
        use_pep517: Optional boolean to force --use-pep517/--no-use-pep517
        requirements: Optional boolean if a requirements.txt was specified
        pip_options: Optional arbitary list of global options to pass to pip
        install_options: Optional arbitary list of install options to pass to pip install
    """
    # exit fast if pkg already installed
    try:
        importlib.import_module(pkg)
        return
    except ModuleNotFoundError:
        pass
    except Exception:
        pass

    if not _check_pip(): _get_pip()

    cmd = [sys.executable, '-m', 'pip']

    if pip_options:
        if isinstance(pip_options, list):
            options = [quote(option) for option in pip_options]
            cmd.extend(options)
        else:
            raise TypeError('pip_options passed to install must be a list')

    cmd.append('install')

    if install_options:
        if isinstance(install_options, list):
            options = [quote(option) for option in install_options]
            cmd.extend(options)
        else:
            raise TypeError('install_options passed to install must be a list')

    if use_pep517 is True:
        cmd.append('--use-pep517')
    elif use_pep517 is False:
        cmd.append('--no-use-pep517')

    if requirements:
        cmd.append('-r')

    pkg = quote(pkg)
    cmd.append(pkg)

    subprocess.check_call(cmd)
