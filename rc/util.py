import subprocess
from rc.exception import RunException
import sys
from collections import namedtuple
import os
from typing import Union, List
import io
from threading import Thread
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed

RunResult = namedtuple('RunResult', ['stdout', 'stderr', 'returncode'])


def convert_list_command_to_str(cmd: List[str]) -> str:
    cmd_str = io.StringIO('')
    for c in cmd:
        if c and (c[0] in ['"', "'", '<', '|', '>', '&', ';', '~']):
            cmd_str.write(c)
        elif len(c) >= 2 and c[:2] in ['1>', '2>']:
            cmd_str.write(c)
        else:
            cmd_str.write('"' + c + '"')
        cmd_str.write(' ')
    return cmd_str.getvalue()


def run(cmd: Union[str, List[str]], *, shell=['/bin/sh', '-c'], input=None, timeout=None):
    p = running(cmd, shell=shell, input=input)
    stdout, stderr = p.communicate(timeout=timeout)
    return RunResult(returncode=p.returncode, stdout=stdout, stderr=stderr)


def running(cmd: Union[str, List[str]], *, shell=['/bin/sh', '-c'], input=None):
    if type(cmd) is list:
        cmd = convert_list_command_to_str(cmd)
    try:
        p = subprocess.Popen([*shell, cmd], stdin=subprocess.PIPE if input else None,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
        if input:
            p.stdin.write(input)
            p.stdin.close()
            p.stdin = None
        return p
    except:
        raise RunException(sys.exc_info()[0])


STDOUT = 1
STDERR = 2
EXIT = 3


def run_stream(cmd: Union[str, List[str]], *, shell=['/bin/sh', '-c'], input=None):
    p = running(cmd, shell=shell, input=input)
    q = Queue()

    def queue_stdout():
        for line in p.stdout:
            q.put((STDOUT, line))

    def queue_stderr():
        for line in p.stderr:
            q.put((STDERR, line))

    queue_stdout_thread = Thread(target=queue_stdout)
    queue_stderr_thread = Thread(target=queue_stderr)

    queue_stdout_thread.start()
    queue_stderr_thread.start()

    def queue_exit():
        queue_stdout_thread.join()
        queue_stderr_thread.join()

        while p.poll() is None:
            pass
        q.put((EXIT, p.returncode))

    queue_exit_thread = Thread(target=queue_exit)
    queue_exit_thread.start()
    return q, p


def handle_stream(q, *, stdout_handler=None, stderr_handler=None, exit_handler=None):
    while True:
        event, value = q.get()
        if event == EXIT:
            if exit_handler:
                exit_handler(value)
            break
        elif event == STDOUT:
            if stdout_handler:
                stdout_handler(value)
        elif event == STDERR:
            if stderr_handler:
                stderr_handler(value)
        q.task_done()


executor = ThreadPoolExecutor()


def go(func, *args, **kwargs):
    return executor.submit(func, *args, **kwargs)


def pmap(func, *iterables, timeout=None):
    return list(executor.map(func, *iterables, timeout=timeout))


def print_stream(q, *, prefix):
    return handle_stream(q, stdout_handler=lambda line: print(prefix, 'STDOUT |', line, end=''),
                         stderr_handler=lambda line: print(
                             prefix, 'STDERR |', line, end=''),
                         exit_handler=lambda exitcode: print(prefix, 'EXIT CODE |', exitcode, end=''))


def save_stream_to_file(q, *, path, name):
    with open(os.path.join(path, name+'.stdout'), 'w') as stdout:
        with open(os.path.join(path, name+'.stderr'), 'w') as stderr:
            with open(os.path.join(path, name+'.exitcode'), 'w') as exitcode:
                return handle_stream(q, stdout_handler=lambda line: stdout.write(line),
                                     stderr_handler=lambda line: stderr.write(
                                         line),
                                     exit_handler=lambda ec: exitcode.write(ec))
