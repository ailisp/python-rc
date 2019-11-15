from rc.util import run
from rc.exception import MachineCreationException, MachineNotRunningException, MachineShutdownException, MachineDeletionException, MachineChangeTypeException, MachineNotReadyException
from rc.machine import Machine
import sys
from retry import retry
import os
import yaml
from functools import lru_cache
import re
import sys

gcloud_provider = sys.modules[__name__]


def _zone_region(zone):
    return zone[:-2]


def _create_firewall(name, allows):
    return run(['gcloud', 'compute', 'firewall-rules', 'create',
                name, '--target-tags', name,
                '--allow', ','.join(allows)])


def _reserve_ip_address(ip, name, region):
    return run(['gcloud', 'compute', 'addresses',
                'create', name, '--addresses', ip, '--region', region])


def _delete_firewall(name):
    return run(['gcloud', 'compute', 'firewall-rules', 'delete',
                name], input='yes\n')


def _address_exist(name, region):
    return run(['gcloud', 'compute', 'addresses', 'describe', '--region', region, name]).returncode == 0


def _firewall_exist(name):
    return run(['gcloud', 'compute', 'firewall-rules', 'describe', name]).returncode == 0


def _release_ip_address(name, region):
    return run(['gcloud', 'compute', 'addresses', 'delete', '--region', region, name], input='yes\n')


SSH_KEY_PATH = os.path.expanduser('~/.ssh/google_compute_engine')


def list():
    p = run(['gcloud', 'compute', 'instances', 'list', '--format',
             'value(zone, name, networkInterfaces[0].accessConfigs[0].natIP)'])
    result = []
    lines = p.stdout.strip('\n').split('\n')
    for line in lines:
        zone, name, ip = re.split(r'\s+', line)
        result.append(Machine(provider=gcloud_provider, name=name,
                              zone=zone, ip=ip, username=_get_username(), ssh_key_path=SSH_KEY_PATH))
    return result


def get(name):
    p = run(['gcloud', 'compute', 'instances', 'list', '--format',
             'value(zone, name, networkInterfaces[0].accessConfigs[0].natIP)',
             '--filter', 'name=' + name])
    if p.stdout.strip('\n') == '':
        return None
    zone, name, ip = re.split(r'\s+', p.stdout.strip('\n'))
    return Machine(provider=gcloud_provider, name=name,
                   zone=zone, ip=ip, username=_get_username(), ssh_key_path=SSH_KEY_PATH)


@lru_cache(maxsize=1)
def _get_username():
    p = run(['gcloud', 'compute', 'os-login', 'describe-profile'])
    return yaml.safe_load(p.stdout)['posixAccounts'][0]['username']


def _get_ip(name):
    p = run(['gcloud', 'compute', 'instances', 'list', '--filter', 'name='+name, '--format',
             'get(networkInterfaces[0].accessConfigs[0].natIP)'])
    return p.stdout.strip()


@retry(MachineNotRunningException, delay=2)
def _wait_bootup(name):
    p = run(['gcloud', 'compute', 'instances', 'list', '--format',
             'value(status)', '--filter', 'name=' + name])
    status = p.stdout.strip()
    if status != 'RUNNING':
        raise MachineNotRunningException(status)


@retry(MachineNotReadyException)
def _wait_ssh(machine):
    p = machine.run('echo a')
    if p.returncode != 0:
        raise MachineNotReadyException(p.stderr)


def create(*, name, machine_type, disk_size, image_project, image_family=None, image=None, zone, preemptible=False, firewall_allows):
    args = [name]
    args += ['--machine-type', machine_type]
    args += ['--boot-disk-size', disk_size]
    if image_family:
        args += ['--image-family', image_family]
    args += ['--image-project', image_project]
    if image:
        args += ['--image', image]
    args += ['--zone', zone]
    if preemptible:
        args += ['--preemptible']

    if _firewall_exist(name):
        _delete_firewall(name)
    p = _create_firewall(name=name, allows=firewall_allows)
    if p.returncode != 0:
        raise MachineCreationException(p.stderr)

    p = run(['gcloud', 'compute', 'instances', 'create', *args])
    if p.returncode != 0:
        _delete_firewall(name)
        raise MachineCreationException(p.stderr)

    _wait_bootup(name)

    if not preemptible:
        if _address_exist(name, _zone_region(zone)):
            _release_ip_address(name, _zone_region(zone))
        ip = _get_ip(name)
        p = _reserve_ip_address(ip, name, _zone_region(zone))
        if p.returncode != 0:
            _delete_firewall(name)
            _delete_machine(name, zone)
            raise MachineCreationException(p.stderr)
    machine = Machine(provider=gcloud_provider, name=name, zone=zone,
                      ip=ip, username=_get_username(), ssh_key_path=SSH_KEY_PATH)
    _wait_ssh(machine)
    return machine


def delete(machine):
    p = _delete_machine(machine.name, machine.zone)
    if p.returncode != 0:
        raise MachineDeletionException(p.stderr)
    if _address_exist(machine.name, _zone_region(machine.zone)):
        p = _release_ip_address(machine.name, _zone_region(machine.zone))
        if p.returncode != 0:
            raise MachineDeletionException(p.stderr)
    if _firewall_exist(machine.name):
        p = _delete_firewall(machine.name)
        if p.returncode != 0:
            raise MachineDeletionException(p.stderr)


def _delete_machine(name, zone):
    return run(['gcloud', 'compute', 'instances',
                'delete', name, '--zone', zone], input='yes\n')


def shutdown(machine):
    p = run(['gcloud', 'compute', 'instances', 'stop',
             machine.name, '--zone', machine.zone])
    if p.returncode != 0:
        raise MachineShutdownException(p.stderr)


def bootup(machine):
    p = run(['gcloud', 'compute', 'instances', 'start',
             machine.name, '--zone', machine.zone])
    if p.returncode != 0:
        raise MachineShutdownException(p.stderr)


def status(machine):
    p = run(['gcloud', 'compute', 'instances', 'list', '--format',
             'value(status)', '--filter', 'name=' + machine.name])
    return p.stdout.strip()


def change_type(machine, new_type):
    p = run(['gcloud', 'compute', 'instances', 'set-machine-type', machine.name,
             '--zone', machine.zone, '--machine-type', new_type])
    if p.returncode != 0:
        raise MachineChangeTypeException(p.stderr)
