import os
from rc import run, ok, pmap
import yaml
import rc

config_dir = os.path.expanduser('~/.python-rc/')
groups_dir = os.path.join(config_dir, 'groups')


def create_config_dirs():
    ok(run(f'mkdir -p {groups_dir}'))


def get_spec(spec, default, item):
    if type(spec) is str:
        return default.get(item)
    return spec.get(item, default.get(item))


def machine_from_spec(spec, default):
    provider = get_spec(spec, default, 'provider')
    assert provider
    provider = getattr(rc.provider, provider)
    assert provider
    if type(spec) is str:
        machine = provider.get(spec)
        assert machine
        return machine
    else:
        name = spec.get('name')
        machine = provider.get(name)
        assert machine
        user = get_spec(spec, default, 'user')
        if user:
            machine.user = user
        ssk_key = get_spec(spec, default, 'ssh_key')
        if ssh_key:
            machine.ssh_key_path = ssh_key
        return machine


def parse_config(config_file, sub_machines=None):
    config = yaml.load(open(config_file))
    default = config.get('default', {})
    machine_spec = config.get('machines', None)
    if machine_spec is None:
        raise "Machines cannot be empty"
    machines = pmap(lambda ms: machine_from_spec(ms, default), machine_spec)
    group_machines = {}
    for m in machines:
        group_machines[str(m)] = m
    assert len(group_machines) == len(machines)
    if sub_machines:
        targets = []
        for n in sub_machines:
            matches = list(
                filter(lambda name: n in name, group_machines.keys()))
            assert len(matches) == 1
            targets += matches
        assert len(targets) > 0
    else:
        targets = group_machines.keys()
    return list(map(lambda n: group_machines[n], sorted(targets)))


def get(group_name):
    if os.path.exists(os.path.join(groups_dir, group_name)):
        return os.path.join(groups_dir, group_name)
