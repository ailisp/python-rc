from rc.util import run, running, run_stream, handle_stream, STDERR, STDOUT, EXIT


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
'''), stdout.strip() == 'hello world\naaa'


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
