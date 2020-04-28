import re
from functools import lru_cache
import yaml
import os
from retry import retry
import sys
from rc.machine import Machine
from rc.util import run
from rc.exception import MachineCreationException, MachineNotRunningException, MachineShutdownException, \
    MachineDeletionException, MachineChangeTypeException, MachineNotReadyException, SaveImageException, \
    DeleteImageException, FirewallRuleCreationException, FirewallRuleDeleteionException, MachineBootupException, \
    RcException, DiskCreationException, DiskDeletionException, MachineAddDiskException, MachineRemoveDiskException

gcloud_provider = sys.modules[__name__]


def _zone_region(zone):
    return zone[:-2]


def create_firewall(name, allows=None):
    if allows:
        allow_param = ['--allow', ','.join(allows)]
    else:
        allow_param = ['--allow', 'tcp:22']

    return run(['gcloud', 'compute', 'firewall-rules', 'create',
                name, '--target-tags', name, *allow_param])


def _reserve_ip_address(ip, name, region):
    return run(['gcloud', 'compute', 'addresses',
                'create', name, '--addresses', ip, '--region', region])


def delete_firewall(name):
    return run(['gcloud', 'compute', 'firewall-rules', 'delete',
                name], input='yes\n')


def _address_exist(name, region):
    return run(['gcloud', 'compute', 'addresses', 'describe', '--region', region, name]).returncode == 0


def firewall_exist(name):
    return run(['gcloud', 'compute', 'firewall-rules', 'describe', name]).returncode == 0


def _release_ip_address(name, region):
    return run(['gcloud', 'compute', 'addresses', 'delete', '--region', region, name], input='yes\n')


SSH_KEY_PATH = os.path.expanduser('~/.ssh/google_compute_engine')

if not os.path.exists(SSH_KEY_PATH):
    print("There is no key at {}, creating new key.".format(SSH_KEY_PATH))
    # Generate new ssh key to log in.
    # WARNING: It will create a key with an empty passphrase.
    run(["ssh-keygen", "-f", SSH_KEY_PATH, "-t", "rsa", "-N", '""'])
    # Upload key
    run(["gcloud", "compute", "os-login", "ssh-keys",
         "add", "--key-file={}.pub".format(SSH_KEY_PATH)])


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


def create(name, *, project=None, machine_type, disk_size, image_project, image_family=None, image=None, zone, min_cpu_platform=None,
           preemptible=False, firewall_allows=None, reserve_ip=True, firewalls=None, disk_type=None):
    args = [name]
    args += ['--machine-type', machine_type]
    args += ['--boot-disk-size', disk_size]
    if disk_type:
        args += ['--boot-disk-type', disk_type]
    if image_family:
        args += ['--image-family', image_family]
    args += ['--image-project', image_project]
    if image:
        args += ['--image', image]
    args += ['--zone', zone]

    if min_cpu_platform:
        args += ['--min-cpu-platform', min_cpu_platform]
    if preemptible:
        args += ['--preemptible']

    if firewall_allows:
        if firewall_exist(name):
            delete_firewall(name)
        p = create_firewall(name=name, allows=firewall_allows)
        if p.returncode != 0:
            raise MachineCreationException(p.stderr)
        args += ['--tags', name]
    elif firewalls:
        args += ['--tags', ','.join(firewalls)]

    p = run(['gcloud', 'compute', 'instances', 'create', *args])
    if p.returncode != 0:
        if firewall_allows:
            delete_firewall(name)
        raise MachineCreationException(p.stderr)

    _wait_bootup(name)

    ip = _get_ip(name)
    if not preemptible and reserve_ip:
        if _address_exist(name, _zone_region(zone)):
            _release_ip_address(name, _zone_region(zone))
        p = _reserve_ip_address(ip, name, _zone_region(zone))
        if p.returncode != 0:
            if firewall_allows:
                delete_firewall(name)
            _delete_machine(name, zone)
            raise MachineCreationException(p.stderr)
    machine = Machine(provider=gcloud_provider, name=name, zone=zone,
                      ip=ip, username=_get_username(), ssh_key_path=SSH_KEY_PATH)
    machine.wait_ssh()
    return machine


def delete(machine):
    p = _delete_machine(machine.name, machine.zone)
    if p.returncode != 0:
        raise MachineDeletionException(p.stderr)
    if _address_exist(machine.name, _zone_region(machine.zone)):
        p = _release_ip_address(machine.name, _zone_region(machine.zone))
        if p.returncode != 0:
            raise MachineDeletionException(p.stderr)
    if firewall_exist(machine.name):
        p = delete_firewall(machine.name)
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
        raise MachineBootupException(p.stderr)
    machine.wait_ssh()


def status(machine):
    p = run(['gcloud', 'compute', 'instances', 'list', '--format',
             'value(status)', '--filter', 'name=' + machine.name])
    return p.stdout.strip()


def change_type(machine, new_type):
    p = run(['gcloud', 'compute', 'instances', 'set-machine-type', machine.name,
             '--zone', machine.zone, '--machine-type', new_type])
    if p.returncode != 0:
        raise MachineChangeTypeException(p.stderr)


def save_image(machine, image, *, image_family=None, description=None):
    command = ['gcloud', 'compute', 'images', 'create', image, '--source-disk',
               machine.name, '--source-disk-zone', machine.zone]
    if image_family:
        command += ['--family', image_family]
    if description:
        command += ['--description', description]
    p = run(command)
    if p.returncode != 0:
        raise SaveImageException(p.stderr)


def delete_image(image):
    command = ['gcloud', 'compute', 'images', 'delete', image]
    p = run(command)
    if p.returncode != 0:
        raise DeleteImageException(p.stderr)


def add_firewall(machine, firewall):
    pass


def remove_firewall(machine, firewall):
    pass


def create_disk(name, *, type='pd-standard', size, project=None, zone):
    if project:
        project = f'--project {project}'
    else:
        project = ''
    p = run(
        f'gcloud beta compute disks create {name} {project} --type={type} --size={size} --zone={zone}')
    if p.returncode != 0:
        raise DiskCreationException(p.stderr)


def add_disk(machine, disk):
    p = run(
        f'gcloud compute instances attach-disk {machine.name} --disk={disk} --zone {machine.zone} --device-name={disk}')
    if p.returncode != 0:
        raise MachineAddDiskException(p.stderr)
    p = machine.sudo('lsblk -f /dev/disk/by-id/google-' +
                     disk + " | awk '{print $2}'")
    if p.returncode != 0:
        raise MachineAddDiskException(p.stderr)
    fstype = p.stdout.strip()
    assert fstype.startswith('FSTYPE')
    if fstype.strip() != 'FSTYPE':
        # it's already been formatted and there's a filesystem on it
        p = machine.sudo(f'''
        mkdir -p /mnt/{disk}
        mount -o discard,defaults /dev/disk/by-id/google-{disk} /mnt/{disk}
        chmod a+w /mnt/{disk}
        ''')
    else:
        p = machine.sudo(f'''
        sudo mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/disk/by-id/google-{disk}
        mkdir -p /mnt/{disk}
        mount -o discard,defaults /dev/disk/by-id/google-{disk} /mnt/{disk}
        sudo chmod a+w /mnt/{disk}
        ''')
    if p.returncode != 0:
        raise MachineAddDiskException(p.stderr)


def remove_disk(machine, disk):
    p = machine.sudo(f'umount /dev/disk/by-id/google-{disk}')
    if p.returncode != 0 and 'No such file or directory' not in p.stderr:
        raise MachineRemoveDiskException(p.stderr)
    p = run(
        f'gcloud compute instances detach-disk {machine.name} --disk {disk} --zone {machine.zone}'
    )
    if p.returncode != 0:
        raise MachineRemoveDiskException(p.stderr)


def delete_disk(disk, zone):
    p = run(f'gcloud compute disks delete {disk} --zone {zone}', input='y\n')
    if p.returncode != 0:
        raise DiskDeletionException(p.stderr)


def set_project(project):
    p = run(f'gcloud config set project {project}')
    if p.returncode != 0:
        raise RcException(p.stderr)


def get_project():
    p = run(f'gcloud config get-value project')
    if p.returncode != 0:
        raise RcException(p.stderr)
    return p.stdout.strip()
