from rc import gcloud
from rc.util import run
from rc.test.util import Timer


def create_test_machine():
    return gcloud.create(name="test-rc-node", machine_type="n1-standard-1", disk_size="20G", image_project='ubuntu-os-cloud', image_family='ubuntu-1804-lts',
                         zone='us-west2-a', preemptible=False, firewall_allows=['tcp:8080'])


def test_gcloud():
    # Cleanup from last fail
    a = gcloud.get('test-rc-node')
    if a is not None:
        a.delete()

    # Test list
    with Timer('list machine'):
        old_machines = gcloud.list()
    assert len(list(filter(lambda machine: machine.name ==
                           'test-rc-node', old_machines))) == 0

    # Test get None
    assert gcloud.get('test-rc-node') is None

    # Test create machine
    with Timer('create machine'):
        machine1 = create_test_machine()
    assert machine1.name == "test-rc-node"
    assert machine1.ip != ''
    assert machine1.ssh_key_path != ''
    assert machine1.username != ''
    assert machine1.status() == "RUNNING"

    # Test get machine
    with Timer('get machine'):
        machine1_get = gcloud.get('test-rc-node')
    assert machine1 == machine1_get

    # Test list after create
    new_machines = gcloud.list()
    assert len(list(filter(lambda machine: machine.name ==
                           'test-rc-node', new_machines))) == 1
    assert len(new_machines) == len(old_machines) + 1

    # Test shutdown
    with Timer('shutdown'):
        machine1.shutdown()
    assert machine1.status() == "TERMINATED"

    # Test bootup
    with Timer('bootup'):
        machine1.bootup()
    assert machine1.status() == "RUNNING"

    # Test upload download
    machine1.upload(local_path='rc/test/test_gcloud.py', machine_path="/tmp/")
    assert machine1.run("ls /tmp/test_gcloud.py")
    machine1.download(machine_path="/tmp/test_gcloud.py",
                      local_path="/tmp/test_gcloud.py")
    assert open(
        "/tmp/test_gcloud.py").read() == open("/tmp/test_gcloud.py").read()
    run(['rm', '/tmp/test_gcloud.py'])

    # Test run command on machine
    machine1.run(['echo', 'aaa', '>', '/tmp/aaaa.txt'])
    assert run('ls /tmp/aaaa.txt').returncode != 0
    machine1.run(['grep', '', '/tmp/aaaa.txt'])
    p = machine1.run('cat /tmp/aaaa.txt')
    assert p.stdout == 'aaa\n'

    # Test delete
    with Timer('delete machine'):
        machine1.delete()
    assert gcloud.get('test-rc-node') is None
