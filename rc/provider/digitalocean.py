from rc.util import run
from rc.exception import MachineCreationException, MachineDeletionException, \
    MachineShutdownException, MachineBootupException, SaveImageException, MachineChangeTypeException, \
    DeleteImageException, FirewallRuleCreationException
from rc.machine import Machine
from rc.firewall import Firewall
import sys
import re
import os
from functools import lru_cache
import json
import time

digitalocean_provider = sys.modules[__name__]

SSH_KEY_PATH = os.path.expanduser('~/.ssh/id_rsa')


@lru_cache(maxsize=1)
def _digitalocean_ssh_key_fingerprint():
    p = run('ssh-keygen -E md5 -lf ~/.ssh/id_rsa.pub')
    fingerprint = p.stdout.split(' ')[1][4:]
    p = run(f'doctl compute ssh-key get {fingerprint}')
    if p.returncode != 0:
        p = run(f'doctl compute ssh-key import python-rc ~/.ssh/id_rsa.pub')
    return fingerprint


def list():
    p = run(['doctl', 'compute', 'droplet', 'list', '--no-header',
             '--format', 'Region,Name,PublicIPv4,ID'])
    result = []
    lines = p.stdout.strip('\n').split('\n')
    for line in lines:
        zone, name, ip, id_ = re.split(r'\s+', line)
        m = Machine(provider=digitalocean_provider, name=name,
                    zone=zone, ip=ip, username='root', ssh_key_path=SSH_KEY_PATH)
        m.id = id_
        result.append(m)
    return result


def _exist(id_):
    p = run(f'doctl compute droplet get {id_}')
    return p.returncode == 0


def get(name):
    p = run(
        f'doctl compute droplet list --no-header --format Region,Name,PublicIPv4,ID')
    lines = p.stdout.strip('\n').split('\n')
    for line in lines:
        zone, name_, ip, id_ = re.split(r'\s+', line)
        if name_ == name:
            m = Machine(provider=digitalocean_provider, name=name,
                        zone=zone, ip=ip, username='root', ssh_key_path=SSH_KEY_PATH)
            m.id = id_
            return m
    return None


def status(machine):
    p = run(
        f'doctl compute droplet get {machine.id} --no-header --format Status')
    return p.stdout.strip()


def bootup(machine):
    p = run(f'doctl compute droplet-action power-on {machine.id} --wait')
    if p.returncode != 0:
        return MachineBootupException(p.stderr)
    machine.wait_ssh()


def shutdown(machine):
    p = run(f'doctl compute droplet-action shutdown {machine.id} --wait')
    if p.returncode != 0:
        raise MachineShutdownException(p.stderr)


def create(name, *, image, region, size, firewall_names=None):
    # Available images:
    # user images: doctl compute snapshot list
    # digitalocean linux distro images: doctl compute image list-distribution
    # digitalocean application images: doctl compute image list-application
    # Use the slug for digitalocean images. Use name for user images

    # Available regions:
    # doctl compute region list
    # Use slug to refer a region

    # Available machine sizes:
    # doctl compute size list
    # Use slug to refer a machine size
    machine = get(name)
    if machine:
        raise MachineCreationException(f'Machine {name} is already exist')
    cmd = f'doctl compute droplet create {name} --region {region} --size {size} --image {image} --ssh-keys {_digitalocean_ssh_key_fingerprint()}'
    if firewall_names:
        cmd += ' --tag-names ' + ','.join(firewall_names)
    cmd += ' --wait'
    p = run(cmd)
    if p.returncode != 0:
        raise MachineCreationException(p.stderr)
    machine = get(name)
    machine.wait_ssh()
    return machine


def change_type(machine, new_type):
    # new_type: a digitalocean machine size
    # doctl compute size list
    # Use slug to refer a machine size
    p = run(
        f'doctl compute droplet-action resize {machine.id} --size {new_type} --wait')
    if p.returncode != 0:
        raise MachineChangeTypeException(p.stderr)


def save_image(machine, image):
    p = run(
        f'doctl compute droplet-action snapshot {machine.id} --snapshot-name {image} --wait')
    if p.returncode != 0:
        raise SaveImageException(p.stderr)


def delete_image(image):
    p = run(
        f'doctl compute snapshot list --output json')
    snapshots = json.load(p.stdout)
    for s in snapshots:
        if s["name"] == image:
            p = run(f'doctl compute snapshot delete {s["id"]}')
            if p.returncode != 0:
                raise DeleteImageException(p.stderr)
            return


def delete(machine):
    p = run(f'doctl compute droplet delete {machine.id} --force')
    if p.returncode != 0:
        raise MachineDeletionException(p.stderr)
    while _exist(machine):
        time.sleep(1)


def create_firewall(name, *, direction='in', ports, ips=['0.0.0.0/0']):
    cmd = f'doctl compute firewall create {name} --tag-names {name}'
    rules = []
    for port in ports:
        if port == 'icmp':
            rule = 'protocol:icmp,address:'
            rule += ',address:'.join(ips)
        else:
            protocol, port = port.split(':')
            rule = f'protocol:{prototocol},port:{port},address:'
            rule += ',address:'.join(ips)
        rules.append(rule)
    rules = ' '.join(rules)
    if direction == 'in':
        cmd += f" --inbound-rules '{rules}'"
    elif direction == 'out':
        cmd += f" --outbound-rules '{rules}'"
    else:
        raise FirewallRuleCreationException(
            'direction must be either "in" or "out"')
    p = run(cmd)
    if p.returncode != 0:
        raise FirewallRuleCreationException(p.stderr)
    return Firewall(name, provider=digitalocean_provider, direction=direction, action=action, ports=ports, ips=ips)
