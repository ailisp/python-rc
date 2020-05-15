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


def _ensure_group(group_name, location):
    if not _group_exist(group_name):
        return _create_group(group_name, location)


def create(*, name, machine_size, disk_size_gb=None, image, location, username=None, ssh_key_path=None, reserve_ip=True):
    """
    Available machine_size: find online for detail and price, or: az vm list-sizes --location location -o table

    Available image: az vm image list -o table

    Available location: az account list-locations -o table
    """
    args = ['--name', name]
    args += ['--resource-group', name]
    args += ['--image', image]
    args += ['--size', machine_size]
    if reserve_ip:
        args += ['--public-ip-address-allocation', 'static']

    if disk_size_gb is not None:
        args += ['--os-disk-size-gb', str(disk_size_gb)]
    # if _group_exist(name):
    #     raise MachineCreationException('resource group already exist')

    if username is None:
        username = os.getlogin()
    else:
        args += ['--admin-username', username]
    if ssh_key_path is None:
        ssh_key_path = SSH_KEY_PATH
    else:
        args += ['--ssh-key-value', f'@{os.path.expanduser(ssh_key_path)}.pub']

    p = _create_group(name, location)
    if p.returncode != 0:
        raise MachineCreationException(p.stderr)
    p = run(['az', 'vm', 'create', *args])
    if p.returncode != 0:
        _delete_group(name)
        raise MachineCreationException(p.stderr)

    ip = json.loads(p.stdout)['publicIpAddress']

    machine = Machine(provider=azure_provider, name=name, location=location,
                      ip=ip, username=username, ssh_key_path=ssh_key_path)
    return machine


def delete(machine):
    p = _delete_group(machine.name)
    if p.returncode != 0:
        raise MachineDeletionException(p.stderr)


def get(name, *, username=None, ssh_key_path=None, **kwargs):
    p = run(['az', 'vm', 'list-ip-addresses', '-n', name, '-g', name])
    if p.returncode == 0:
        res = json.loads(p.stdout)
        if not res:
            return None
        ip_address = res[
            0]['virtualMachine']['network']['publicIpAddresses'][0]['ipAddress']
        if not username:
            username = os.getlogin()
        if not ssh_key_path:
            ssh_key_path = SSH_KEY_PATH
        p = run(f'az vm get-instance-view -n {name} -g {name}')
        res = json.loads(p.stdout)
        location = res["location"]
        return Machine(provider=azure_provider, name=name, location=location,
                       ip=ip_address, username=username, ssh_key_path=ssh_key_path)
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
    if group == machine.name:
        raise SaveImageException('group must be different than machine')
    p = _ensure_group(group, machine.location)
    if p.returncode != 0:
        raise SaveImageException(p.stderr)
    p = run(f'az vm generalize -g {machine.name} --name {machine.name}')
    if p.returncode != 0:
        raise SaveImageException(p.stderr)

    p = run('az extension add -n image-copy-extension -y')
    p = run(
        f'az image copy --source-resource-group {machine.name} --source-object-name {machine.name} --target-location {machine.location} --target-resource-group {group} --cleanup')
    if p.returncode != 0:
        raise SaveImageException(p.stderr)


def get_image(group, image):
    p = run(f'az image list -g {group}')
    images = json.loads(p.stdout)
    for i in images:
        if i['name'] == image:
            return i['id']
    return None
