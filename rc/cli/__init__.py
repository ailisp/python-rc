from rc.cli import config
from rc import run, pmap, p, ep, RunResult, RunException
from rc.util import convert_list_command_to_str
import subprocess
import os
import libtmux
import argparse
from pytimeparse.timeparse import timeparse
from threading import Lock
import term


def execute(targets, args):
    execute_argparser = argparse.ArgumentParser(
        'execute a command on target of machines')
    execute_argparser.add_argument(
        '-t', '--timeout', help='timeout to execute commands. ', default='2m')
    execute_argparser.add_argument('command')
    execute_argparser.add_argument('args', nargs=argparse.REMAINDER)
    args = execute_argparser.parse_args(args)
    timeout = timeparse(args.timeout)
    if args.args:
        cmd = convert_list_command_to_str([args.command, *args.args])
    else:
        cmd = args.command

    l = Lock()
    for target in targets:
        print(f'Start executing on {target}')

    def exec(i):
        target = targets[i]
        ret = None
        try:
            log_path = os.path.join(config.logs_dir, str(target))
            log = open(log_path, 'w')
            proc = target.run(cmd, timeout=timeout, stdout=log, stderr=log)
            if proc.returncode == 0:
                output = f'{term.green}SUCCESS{term.off} on {target}'
            else:
                output = f'{term.red}FAIL{term.off} on {target}. Exit code: {proc.returncode}'
            ret = proc
        except RunException as e:
            output = f'{term.red}FAIL{term.off} on {target}. Timeout'
            ret = e
        output += f'. Log: file://{log_path}'
        with l:
            term.saveCursor()
            term.up(len(targets) - i)
            term.clearLine()
            term.writeLine(output)
            term.restoreCursor()
        return ret
    results = pmap(exec, range(len(targets)))
    if all(map(lambda r: isinstance(r, RunResult) and r.returncode == 0, results)):
        term.writeLine('All execution succeeded', term.green)
        exit(0)
    else:
        term.writeLine('Some execution failed', term.red)
        exit(1)


def cat(args):
    group_name = args[0]
    group_config_file = config.get(group_name)
    if group_config_file:
        p(open(group_config_file).read())
    else:
        p(f'group {group_name} not exists')
        exit(2)


def ls(_args):
    p(run(f'ls {config.groups_dir}').stdout)


def edit(args):
    group_name = args[0]
    group_config_file = os.path.join(config.groups_dir, group_name)
    subprocess.run(['vi', group_config_file])


def rm(args):
    group_name = args[0]
    os.remove(os.path.join(config.groups_dir, group_name))


def tmux(args):
    targets = config.get_targets(args[0])
    if not targets:
        ep(f'targets not exist: {args[0]}')
        exit(2)

    server = libtmux.Server(socket_name='python-rc', config_file=os.path.join(
        config.config_dir, '.tmux.conf'))
    try:
        sessions = server.list_sessions()
    except:
        sessions = []
    max_python_sessions = -1
    for s in sessions:
        if s.name.startswith('python-rc'):
            n = int(s.name.split('-')[-1])
            max_python_sessions = max(max_python_sessions, n)
    max_python_sessions += 1

    session_name = f"python-rc-{max_python_sessions}"
    session = server.new_session(session_name)

    n = len(targets)
    w = session.attached_window.id
    window = session.new_window()
    pane = window.panes[0]
    session.kill_window(w)
    for i in range(1, n):
        window.split_window()
    window.select_layout('tiled')
    for i, pane in enumerate(window.panes):
        pane.send_keys('\n')
        pane.send_keys(targets[i].ssh_shell_str())
        pane.send_keys('\n')
    window.set_window_option('synchronize-panes', 'on')
    window.panes[0].select_pane()
    subprocess.run(['tmux', '-L', 'python-rc', 'a', '-t', session_name])
