import subprocess
from rc.exception import RunException
import sys
from collections import namedtuple
import multiprocessing as mp
import os
from typing import Union, List
import io

RunResult = namedtuple('RunResult', ['stdout', 'stderr', 'returncode'])


def convert_list_command_to_str(cmd: List[str]) -> str:
    cmd_str = io.StringIO('')
    for c in cmd:
        if c and (c[0] in ['"', "'", '<', '|', '>', '&', ';']):
            cmd_str.write(c)
        else:
            cmd_str.write('"' + c + '"')
        cmd_str.write(' ')
    return cmd_str.getvalue()


def run(cmd: Union[str, List[str]], *, shell=['/bin/sh', '-c'], input=None, timeout=None):
    p = running(cmd, shell=shell, input=input, timeout=timeout)
    stdout, stderr = p.communicate(input=input, timeout=timeout)
    return RunResult(returncode=p.returncode, stdout=stdout, stderr=stderr)


def running(cmd: Union[str, List[str]], *, shell=['/bin/sh', '-c'], input=None, timeout=None):
    if type(cmd) is list:
        cmd = convert_list_command_to_str(cmd)
    try:
        p = subprocess.Popen([*shell, cmd], stdin=subprocess.PIPE if input else None,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
        return p
    except:
        raise RunException(sys.exc_info()[0])
