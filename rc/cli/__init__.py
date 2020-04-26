from rc.cli import config
from rc import run, pmap
from rc.util import convert_list_command_to_str
import subprocess
import os
import libtmux


def execute(targets, args):
    if len(args) == 1:
        cmd = args[0]
    else:
        cmd = convert_list_command_to_str(args)

    def exec(target):
        print(f'Start executing {cmd} on {target}')
        p = target.run(cmd)
        print(f'End executing {cmd} on {target}, exit code {p.returncode}')
        print(f'{target} stdout: {p.stdout}')

        return p
    results = pmap(exec, targets)
    if any(map(lambda r: r.returncode != 0, results)):
        print('Some execution failed')
        exit(1)
    else:
        print('All execution succeeded')
        exit(0)


def cat(args):
    group_name = args[0]
    group_config_file = config.get(group_name)
    if group_config_file:
        print(open(group_config_file).read())
    else:
        print(f'group {group_name} not exists')
        exit(2)


def ls(_args):
    print(run(f'ls {config.groups_dir}').stdout)


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
        print(f'targets not exist: {args[0]}')
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
    window = session.new_window(window_shell=targets[0].ssh_shell_str())
    pane = window.panes[0]
    session.kill_window(w)
    for i in range(1, n):
        window.split_window(shell=targets[i].ssh_shell_str())
    window.select_layout('tiled')
    window.set_window_option('synchronize-panes', 'on')
    subprocess.run(['tmux', '-L', 'python-rc', 'a', '-t', session_name])
