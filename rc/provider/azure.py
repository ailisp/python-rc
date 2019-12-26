from rc.util import run
from rc.exception import MachineCreationException, MachineDeletionException, \
    MachineShutdownException, MachineBootupException, SaveImageException
from rc.machine import Machine
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
    # Very slow
    return run(['az', 'group', 'delete', '-n', group_name, '--yes'])


def create(*, name, machine_size, disk_size_gb=None, image, location):
    args = ['--name', name]
    args += ['--resource-group', name]
    args += ['--image', image]
    args += ['--size', machine_size]

    if disk_size_gb is not None:
        args += ['--os-disk-size-gb', str(disk_size_gb)]
    if _group_exist(name):
        raise MachineCreationException('resource group already exist')

    p = _create_group(name, location)
    if p.returncode != 0:
        raise MachineCreationException(p.stderr)

    p = run(['az', 'vm', 'create', *args])
    if p.returncode != 0:
        _delete_group(name)
        raise MachineCreationException(p.stderr)

    ip = json.loads(p.stdout)['publicIpAddress']

    machine = Machine(provider=azure_provider, name=name, zone=None,
                      ip=ip, username=os.getlogin(), ssh_key_path=SSH_KEY_PATH)
    return machine


def delete(machine):
    p = _delete_group(machine.name)
    if p.returncode != 0:
        raise MachineDeletionException(p.stderr)


def get(name):
    p = run(['az', 'vm', 'list-ip-addresses', '-n', name, '-g', name])
    if p.returncode == 0:
        res = json.loads(p.stdout)
        if not res:
            return None
        ip_address = res[
            0]['virtualMachine']['network']['publicIpAddresses'][0]['ipAddress']
        return Machine(provider=azure_provider, name=name, zone=None,
                       ip=ip_address, username=os.getlogin(), ssh_key_path=SSH_KEY_PATH)
    else:
        return None


def shutdown(machine):
    p = run(['az', 'vm', 'stop',
             '-n', machine.name, '-g', machine.name])
    if p.returncode != 0:
        raise MachineShutdownException(p.stderr)


def bootup(machine):
    p = run(['az', 'vm', 'start',
             '-n', machine.name, '-g', machine.name])
    if p.returncode != 0:
        raise MachineBootupException(p.stderr)


def save_image(machine, image, *, group):
    p = run(['az', 'image', 'create', '-n', image, '-g',
             group if group else machine.name, '--source', machine.name])
    if p.returncode != 0:
        raise SaveImageException(p.stderr)
