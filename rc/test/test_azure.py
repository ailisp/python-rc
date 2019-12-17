from rc import azure
from rc.util import run
from rc.test.util import Timer


def create_test_machine():
    return azure.create(name='test-rc-node', machine_size='Standard_D1', image='ubuntults', location='westus')


def test_azure():
    # Cleanup from last fail
    a = azure.get('test-rc-node')
    print(a)
    if a is not None:
        a.delete()

    # Test create machine
    with Timer('create machine'):
        machine1 = create_test_machine()
    assert machine1.name == "test-rc-node"
    assert machine1.ip != ''
    assert machine1.ssh_key_path != ''
    assert machine1.username != ''

    # Test get machine
    with Timer('get machine'):
        machine1_get = azure.get('test-rc-node')
    assert machine1 == machine1_get

    # Test delete
    with Timer('delete machine'):
        machine1.delete()
    assert azure.get('test-rc-node') is None
