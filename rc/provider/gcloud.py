from rc.util import exec
from rc.exception import MachineCreationException, \
    MachineNotRunningException, MachineShutdownException
from rc.type import Machine
import sys
from retry import retry
import os
import yaml

gcloud_provider = __import__(__name__)


def _create_firewall(*, name, allows):
    p = exec(['gcloud', 'compute', 'firewall-rules', 'create',
              name, '--target-tags', name,
              '--allow', ','.join(allows)])
    if p.returncode != 0:
        raise MachineCreationException(p.stderr.read())


def _delete_firewall(name):
    exec(['gcloud', 'compute', 'firewall-rules', 'delete',
          name])


SSH_KEY_PATH = os.path.expanduser('~/.ssh/google_compute_engine')


def _get_username():
    p = exec(['gcloud', 'compute', 'os-login', 'describe'])
    return yaml.load(p.stdout)['posixAccounts'][0]['username']


def _get_ip(name):
    p = exec(['gcloud', 'compute', 'instances', 'describe', name, '--format',
              'get(networkInterfaces[0].accessConfigs[0].natIP)'])
    return p.stdout.read().strip()


@retry(MachineNotRunningException)
def _wait_bootup(*, name):
    p = exec(['gcloud', 'compute', 'instances', 'list', '--format',
              'value(status)', '--filter', 'name=' + name])
    status = p.stdout.read().strip()
    if status != 'RUNNING':
        raise MachineNotRunningException(status)


def create(*, name, machine_type, disk_size, image_project, image_family=None, image, zone, preemptible=False, firewall_allows):
    args = [name]
    args += ['--machine-type', machine_type]
    args += ['--boot-disk-size', disk_size]
    if image_family:
        args += ['--image-family', image_family]
    args += ['--image-project', image_project]
    args += ['--image', image]
    if preemptible:
        args += ['--preemptible']

    _create_firewall(name=name, allows=firewall_allows)

    p = exec(['gcloud', 'compute', 'instances', 'create', *args])
    if p.returncode != 0:
        raise MachineCreationException(p.stderr.read())
    _wait_bootup(name)
    return Machine(provider=gcloud_provider, name=name, zone=zone, ip=_get_ip(name), username=_get_username(), ssh_key_path=SSH_KEY_PATH)


def shutdown(machine):
    p = exec(['gcloud', 'compute', 'instances', 'stop', machine.name])
    if p.returncode != 0:
        raise MachineShutdownException(p.stderr.read())
