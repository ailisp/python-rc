from rc.util import run, pmap
from rc.machine import Machine
from rc.firewall import Firewall
import json
from functools import lru_cache
import builtins
from pprint import pprint
import sys
import os
from rc.exception import MachineCreationException, SaveImageException, MachineDeletionException, FirewallRuleCreationException, \
    MachineShutdownException
import time

aws_provider = sys.modules[__name__]


SSH_KEY_PATH = os.path.expanduser('~/.ssh/id_rsa')


@lru_cache(maxsize=1)
def _get_regions():
    regions = json.loads(run(
        ['aws', 'ec2', 'describe-regions', '--region', 'us-west-1']).stdout)['Regions']
    return builtins.list(map(lambda region: region['RegionName'], regions))


def _zone_region(zone):
    return zone[:-1]


def _find_instance_name(instance):
    for tag in instance.get('Tags', []):
        if tag['Key'] == 'Name':
            return tag['Value']
    return None


def list(*, username=None, ssh_key_path=None):
    if username is None:
        username = 'root'
    if ssh_key_path is None:
        ssh_key_path = SSH_KEY_PATH
    regions = _get_regions()

    def _get_instance_in_region(region):
        instances = []
        region_instances = json.loads(run(
            ['aws', 'ec2', 'describe-instances', '--region', region]).stdout)
        for reservation in region_instances['Reservations']:
            for instance in reservation['Instances']:
                instances.append(instance)
        return instances
    instances = sum(pmap(_get_instance_in_region, regions), [])
    machines = []

    for i in instances:
        m = _instance_to_machine(i, username, ssh_key_path)
        if m:
            machines.append(m)
    return machines


def _instance_to_machine(i, username, ssh_key_path):
    if i['State']['Name'] != 'terminated':
        name = _find_instance_name(i)
        zone = i['Placement']['AvailabilityZone']
        region = _zone_region(zone)
        ip = i.get('PublicIpAddress')
        id_ = i['InstanceId']
        return Machine(provider=aws_provider,
                       name=name, zone=zone, region=region,
                       ip=ip, username=username, ssh_key_path=ssh_key_path, id=id_)
    return None


def _ensure_aws_keypair(username, ssh_key_path, region):
    p = run(
        f'aws ec2 describe-key-pairs --key-name {username} --region {region}')
    if p.returncode != 0:
        p = run(
            f'aws ec2 import-key-pair --key-name {username} --public-key-material file://{ssh_key_path}.pub --region {region}')
    return p


def get(name, *, username=None, ssh_key_path=None, region=None, **kwargs):
    if region:
        if name.startswith('i-'):
            cmd = f'aws ec2 describe-instances --region {region} --instance-ids {name}'
        else:
            cmd = f'aws ec2 describe-instances --region {region} --filters Name=tag:Name,Values={name}'
        p = run(cmd)
        if p.returncode != 0:
            return None
        else:
            reservations = json.loads(p.stdout)
            instances = []
            for reservation in reservations['Reservations']:
                for instance in reservation['Instances']:
                    if instance['State']['Name'] != 'terminated':
                        instances.append(instance)
            if len(instances) > 1:
                return None
            return _instance_to_machine(instances[0], username, ssh_key_path)
    else:
        machines = list(username=username, ssh_key_path=ssh_key_path)
        if name.startswith('i-'):
            for machine in machines:
                if machine.id == name:
                    return machine
        else:
            for machine in machines:
                if machine.name == name:
                    return machine
        return None


def create(name, *, machine_type, disk_size_gb, image, init_username, region, reserve_ip=True, disk_type=None, firewall=None, username=None, ssh_key_path=None):
    if username is None:
        username = os.getlogin()
    if ssh_key_path is None:
        ssh_key_path = SSH_KEY_PATH

    p = _ensure_aws_keypair(username, ssh_key_path, region)
    if p.returncode != 0:
        raise MachineCreationException(p.stderr)
    cmd = f'aws ec2 run-instances --image-id {image} --instance-type {machine_type} --count 1 --key-name {username} --region {region} --tag-specifications "ResourceType=instance,Tags=[{{Key=Name,Value={name}}}]"'
    if firewall:
        cmd += f' --security-groups {firewall}'
    if disk_type is None:
        disk_type = 'standard'
    ebs = f'{{VolumeType={disk_type},VolumeSize={disk_size_gb}}}'
    block_device_mapping = f'DeviceName=/dev/sda1,Ebs={ebs}'
    cmd += f' --block-device-mapping={block_device_mapping}'
    p = run(cmd)
    if p.returncode != 0:
        raise MachineCreationException(p.stderr)
    instance = json.loads(p.stdout)
    instance_id = instance['Instances'][0]['InstanceId']
    zone = _zone_region(region)
    while True:
        machine = get(instance_id, region=region,
                      username=init_username, ssh_key_path=ssh_key_path)
        if machine.ip:
            break
        time.sleep(1)
    machine.wait_ssh()
    if username != init_username:
        machine.ensure_user(username)
        machine.username = username
    return machine


def create_firewall(name, *, region, inbound_rules=None, outbound_rules=None):
    p = run(
        f'aws ec2 create-security-group --group-name {name} --region {region} --description {name}')
    if p.returncode != 0:
        raise FirewallRuleCreationException(p.stderr)
    if inbound_rules:
        for r in inbound_rules:
            protocol, port, ip = r
            p = run(
                f'aws ec2 authorize-security-group-ingress --group-name {name} --region {region} --protocol {protocol} --port {port} --cidr {ip}')
            if p.returncode != 0:
                raise FirewallRuleCreationException(p.stderr)
    if outbound_rules:
        for r in outbound_rules:
            protocol, port, ip = r
            p = run(
                f'aws ec2 authorize-security-group-egress --group-name {name} --region {region} --protocol {protocol} --port {port} --cidr {ip}')
            if p.returncode != 0:
                raise FirewallRuleCreationException(p.stderr)
    return None


def save_image(machine, image):
    p = run(
        f'aws ec2 create-image --instance-id {machine.id} --name {image} --region {machine.region}')
    if p.returncode != 0:
        raise SaveImageException(p.stderr)


def delete(machine):
    p = run(
        f'aws ec2 terminate-instances --instance-ids {machine.id} --region {machine.region}')
    if p.returncode != 0:
        raise MachineDeletionException(p.stderr)


def shutdown(machine):
    p = run(
        f'aws ec2 stop-instances --instance-ids {machine.id} --region {machine.region}')
    if p.returncode != 0:
        raise MachineShutdownException(p.stderr)


def status(machine):
    p = run(
        f'aws ec2 describe-instance-status --instance-ids {machine.id} --region {machine.region}')
    instance_status = json.loads(p.stdout)
    return instance_status['InstanceStatuses'][0]['InstanceState']['Name']
