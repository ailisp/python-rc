import subprocess
from rc.exception import RunException, PmapException
import sys
from collections import namedtuple
import os
from typing import Union, List
import io
from threading import Thread, Lock
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal

_RunResult = namedtuple('_RunResult', ['stdout', 'stderr', 'returncode'])


class RunResult(_RunResult):
    @property
    def exitcode(self):
        return self.returncode


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


def run(cmd: Union[str, List[str]], *, shell=['/bin/sh', '-c'], input=None, timeout=None, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE):
    p = running(cmd, shell=shell, input=input,
                text=text, stdout=stdout, stderr=stderr)
    try:
        stdout, stderr = p.communicate(timeout=timeout)
    except Exception as e:
        raise RunException(e) from None
    return RunResult(returncode=p.returncode, stdout=stdout, stderr=stderr)


def bash(script, *, timeout=None, flag='set -euo pipefail', login=False, interactive=False, run_shell=['/bin/sh', '-c'], stdout=subprocess.PIPE, stderr=subprocess.PIPE):
    cmd = 'bash '
    if login:
        cmd += '-l '
    if interactive:
        cmd += '-i '
    if flag:
        script = flag + '\n' + script

    return run(cmd, input=script, timeout=timeout, shell=run_shell, stdout=stdout, stderr=stderr)


def sudo(script, *, shell=None, user='root', timeout=None, flag='set -euo pipefail', run_shell=['/bin/sh', '-c'], stdout=subprocess.PIPE, stderr=subprocess.PIPE):
    cmd = 'sudo '
    if user != 'root':
        cmd += '-u ' + user + ' '
    if shell is None:
        cmd += '-i '
    else:
        cmd += '-s ' + shell + ' '
    if flag:
        script = flag + '\n' + script
    return run(cmd, input=script, timeout=timeout, shell=run_shell, stdout=stdout, stderr=stderr)


def python(script, *, timeout=None, python_path='python', user=None, run_shell=['/bin/sh', '-c'], stdout=subprocess.PIPE, stderr=subprocess.PIPE):
    if user:
        return sudo(script, user=user, flag='', shell=python_path, timeout=timeout, run_shell=run_shell, stdout=stdout, stderr=stderr)
    else:
        return run(python_path, input=script, timeout=timeout, shell=run_shell, stdout=stdout, stderr=stderr)


def python2(script, **kwargs):
    return python(script, **kwargs)


def python3(script, **kwargs):
    return python(script, **kwargs)


def running(cmd: Union[str, List[str]], *, shell=['/bin/sh', '-c'], input=None, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE):
    if type(cmd) is list:
        cmd = convert_list_command_to_str(cmd)
    try:
        if not shell:
            shell = []
        p = subprocess.Popen([*shell, cmd], stdin=subprocess.PIPE if input else None,
                             stdout=stdout, stderr=stderr,
                             universal_newlines=text, preexec_fn=os.setsid)
        if input:
            p.stdin.write(input)
            p.stdin.close()
            p.stdin = None
        return p
    except:
        e = sys.exc_info()
        # print(e[0].__name__)
        # print(e[1])
        # import traceback
        # traceback.print_exception(*e)
        raise RunException(e[1]) from None


STDOUT = 1
STDERR = 2
EXIT = 3


def run_stream(cmd: Union[str, List[str]], *, shell=['/bin/sh', '-c'], input=None, text=True):
    p = running(cmd, shell=shell, input=input, text=text)
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


def pmap(func, *iterables, timeout=None, on_exception='raise'):
    if on_exception == 'raise':
        return list(executor.map(func, *iterables, timeout=timeout))

    def func_wrapper(arg):
        try:
            return func(arg)
        except Exception as e:
            return PmapException(e, arg)
    return list(executor.map(func_wrapper, *iterables, timeout=timeout))


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


print_lock = Lock()


def p(*args):
    with print_lock:
        print(*args, flush=True)


def ep(*args):
    with print_lock:
        print(*args, file=sys.stderr, flush=True)


def kill(p):
    os.killpg(os.getpgid(p.pid), signal.SIGTERM)


def ok(p):
    if p.returncode != 0:
        raise RunException(p.stderr)
    return p
