from rc.cli import config
from rc import run, pmap
from rc.util import convert_list_command_to_str
import subprocess
import os


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
    pass
