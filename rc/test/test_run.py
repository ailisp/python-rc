from rc import run, running, run_stream, handle_stream, STDERR, STDOUT, EXIT, print_stream, save_stream_to_file, gcloud
import contextlib
from io import StringIO
import time


def test_run_sh_syntax():
    assert run(['ls', '~']).returncode == 0
    assert run('ls ~').returncode == 0
    assert run(['cat', '"~"']) == run('cat "~"')


def test_run_multiple_line():
    assert run('cat', input='''hello world
aaa''').stdout == 'hello world\naaa'

    assert run('bash', input='''date
ls /
echo hello world
''').stdout.strip().split('\n')[-1] == 'hello world'

    assert run('python', input='''
print('hello world')
print('aaa')
''').stdout.strip() == 'hello world\naaa'


def test_run_stream():
    q, _ = run_stream('python', input='''
import sys
import time
sys.stdout.write('to stdout\\n')
sys.stdout.flush()
time.sleep(1) # sleep to make stdout happens earlier than stderr for sure
sys.stderr.write("to stderr\\n")
sys.stderr.flush()
time.sleep(1)
sys.stdout.write('hello world\\n')
sys.stdout.flush()
exit(1)
    ''')

    t = q.get()
    assert t == (STDOUT, 'to stdout\n')
    q.task_done()

    t = q.get()
    assert t == (STDERR, 'to stderr\n')
    q.task_done()

    t = q.get()
    assert t == (STDOUT, 'hello world\n')
    q.task_done()

    t = q.get()
    assert t == (EXIT, 1)
    q.task_done()

    assert q.empty()


def test_handle_stream():
    q, _ = run_stream('sh', input='''
    echo to stdout
    echo 1>&2 to stderr
    echo hello world
    exit 1
    ''')
    stdout = []
    stderr = []
    exitcode = []
    handle_stream(q, stdout_handler=lambda line: stdout.append(
        line), stderr_handler=lambda line: stderr.append(line), exit_handler=lambda x: exitcode.append(x))
    assert stdout == ['to stdout\n', 'hello world\n']
    assert stderr == ['to stderr\n']
    assert exitcode == [1]


def test_print_stream():
    q, _ = run_stream('sh', input='''
    echo to stdout
    echo 1>&2 to stderr
    echo hello world
    exit 1
    ''')
    temp_stdout = StringIO()
    with contextlib.redirect_stdout(temp_stdout):
        print_stream(q, prefix='node1')

    output = temp_stdout.getvalue().split('\n')
    assert output[-1] == 'node1 EXIT CODE | 1'
    assert output.sort() == """node1 STDERR | to stderr
node1 STDOUT | to stdout
node1 STDOUT | hello world
node1 EXIT CODE | 1""".split('\n').sort()


def save_stream_to_file():
    q, _ = run_stream('sh', input='''
    echo to stdout
    echo 1>&2 to stderr
    echo hello world
    exit 1
    ''')
    save_stream_to_file(path='/tmp', name='node1')
    assert open('/tmp/node1.stdout').read() == '''node1 STDOUT | to stdout
node1 STDOUT | hello world'''
    assert open('/tmp/node1.stderr').read() == 'node1 STDERR | to stderr\n'
    assert open('/tmp/node1.exitcode').read() == 'node1 EXIT CODE | 1'


def test_tmux():
    machine = gcloud.create(name="test-rc-node", machine_type="n1-standard-1", disk_size="20G", image_project='ubuntu-os-cloud', image_family='ubuntu-1804-lts',
                            zone='us-west2-a', preemptible=False, firewall_allows=['tcp:8080'])
    machine = gcloud.get('test-rc-node')
    machine.run('sudo apt install tmux')
    machine.run_detach_tmux('while true; do echo aaaaaa; sleep 10; done')
    machine.kill_detach_tmux()
    assert machine.run('cat /tmp/python-rc.log').stdout == 'aaaaaa\n'
    machine.delete()
