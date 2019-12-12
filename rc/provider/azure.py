from rc.util import run
from rc.exception import MachineCreationException
from machine import Machine
import json
import sys
import os

azure_provider = sys.modules[__name__]

SSH_KEY_PATH = os.path.expanduser('~/.ssh/id_rsa')


def _group_exist(group_name):
    p = run(['az', 'group', 'exists', '-n', group_name])
    if p.stdout.strip() == 'true':
        return True
    return False


def _create_group(group_name, location):
    return run(['az', 'group', 'create', '-n', group_name, '-l', location])


def _delete_group(group_name):
    return run(['az', 'group', 'delete', '-n', group_name])


def create(*, name, machine_size, disk_size_gb=None, image, location):
    args = ['--name', name]
    args += ['--resource-group', name]
    args += ['--image', image]

    if disk_size_gb is not None:
        args += ['--os-disk-size-gb', str(disk_size_gb)]
    if _group_exist(name):
        raise MachineCreationException('resource group already exist')

    p = _create_group(name)
    if p.exitcode != 0:
        raise MachineCreationException(p.stderr)

    p = run(['az', 'vm', 'create', *args])
    if p.exitcode != 0:
        _delete_group(name)
        raise MachineCreationException(p.stderr)

    ip = json.loads(p.stdout)['publicIpAddress']

    machine = Machine(provider=azure_provider, name=name, zone=None,
                      ip=ip, username=os.getlogin(), ssh_key_path=SSH_KEY_PATH)
    return machine
