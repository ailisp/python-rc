from rc.util import run
from rc.exception import MachineCreationException, MachineDeletionException, \
    MachineShutdownException, MachineBootupException, SaveImageException
from rc.machine import Machine
import sys
import re
import os

digitalocean_provider = sys.modules[__name__]

SSH_KEY_PATH = os.path.expanduser('~/.ssh/id_rsa')


def list():
    p = run(['doctl', 'compute', 'droplet', 'list', '--no-header',
             '--format', 'Region,Name,PublicIPv4'])
    result = []
    lines = p.stdout.strip('\n').split('\n')
    for line in lines:
        zone, name, ip = re.split(r'\s+', line)
        result.append(Machine(provider=digitalocean_provider, name=name,
                              zone=zone, ip=ip, username='root', ssh_key_path=SSH_KEY_PATH))
    return result
