from rc.exception import UploadException, DownloadException, MachineNotReadyException
from io import StringIO
from rc.util import run, run_stream, convert_list_command_to_str, \
    bash, sudo, python, python2, python3, running, kill, ok
from retry import retry
import datetime
import os
import subprocess


class Machine:
    def __init__(self, *, provider, name, ip, username, ssh_key_path, **kwargs):
        self.provider = provider
        self.name = name
        self.ip = ip
        self.username = username
        self.ssh_key_path = os.path.expanduser(ssh_key_path)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __eq__(self, other):
        return (self.provider, self.name, self.zone, self.ip, self.username, self.ssh_key_path) == (other.provider, other.name, other.zone, other.ip, other.username, other.ssh_key_path)

    def __repr__(self):
        return 'Machine(provider={provider}, name={name}, ip={ip}, username={username}, ssh_key_path={ssh_key_path})'.format(
            provider=self.provider,
            name=self.name,
            ip=self.ip,
            username=self.username,
            ssh_key_path=self.ssh_key_path
        )

    def __str__(self):
        return f"{self.provider.__name__.split('.')[-1]}." + self.name

    def status(self):
        return self.provider.status(self)

    def bootup(self):
        return self.provider.bootup(self)

    def shutdown(self):
        return self.provider.shutdown(self)

    def delete(self):
        return self.provider.delete(self)

    def change_type(self):
        return self.provider.change_type(self)

    def upload(self, local_path, machine_path, switch_user=None, su=None, user=None):
        user = user or su or switch_user
        if user:
            rsync = f'''--rsync-path='sudo -u {user} rsync' '''
        else:
            rsync = ''

        p = run(f'''
rsync -e 'ssh -o StrictHostKeyChecking=no -i {self.ssh_key_path}' -r \
    {rsync} --progress {local_path} {self.username}@{self.ip}:{machine_path}
''')
        if p.returncode != 0:
            raise UploadException(p.stderr)
        return p

    def download(self, machine_path, local_path, sudo=True):
        if sudo:
            rsync = '''--rsync-path='sudo rsync' '''
        else:
            rsync = ''
        p = run(f'''
rsync -e 'ssh -o StrictHostKeyChecking=no -i {self.ssh_key_path}' -r \
    {rsync} --progress {self.username}@{self.ip}:{machine_path} {local_path}
''')
        if p.returncode != 0:
            raise DownloadException(p.stderr)
        return p

    def _ssh_shell(self):
        return ['ssh', '-o', 'StrictHostKeyChecking=no',
                *(['-i', self.ssh_key_path] if self.ssh_key_path else []), self.username + '@' + self.ip, '--']

    def ssh_shell_str(self):
        return ' '.join(self._ssh_shell()[:-1])

    def running(self, cmd, *, input=None):
        return running(cmd, shell=self._ssh_shell(), input=input)

    def run(self, cmd, *, timeout=None, input=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE):
        return run(cmd, shell=self._ssh_shell(), timeout=timeout, input=input, stdout=stdout, stderr=stderr)

    def run_stream(self, cmd, input=None):
        return run_stream(cmd, shell=self._ssh_shell(), input=input)

    def sudo(self, script, *, shell=None, user='root', timeout=None, flag='set -euo pipefail', stdout=subprocess.PIPE, stderr=subprocess.PIPE):
        return sudo(script, shell=shell, user=user, timeout=timeout, flag=flag,
                    run_shell=self._ssh_shell(), stdout=stdout, stderr=stderr)

    def bash(self, script, *, timeout=None, flag='set -euo pipefail', login=False, interactive=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE):
        return bash(script, timeout=timeout, login=login, interactive=interactive, flag=flag,
                    run_shell=self._ssh_shell(), stdout=stdout, stderr=stderr)

    def run_bg(self, script, *, cmd='bash', stdout='/tmp/python-rc.log', stderr='/tmp/python-rc.log', exitcode='/tmp/python-rc.exitcode', pid='/tmp/python-rc.pid', user=None):
        ts = datetime.datetime.strftime(
            datetime.datetime.utcnow(), '%Y%m%d_%H%M%S')
        ok(self.ensure_dir(f'/tmp/python-rc'))
        ok(self.edit(f'/tmp/python-rc/script_{ts}', script, user=user))
        run_cmd = f'( {cmd} /tmp/python-rc/script_{ts} >>{stdout} 2>>{stderr} & echo -n $! > {pid}; wait $!; echo -n $? >{exitcode}) </dev/null >/dev/null 2>/dev/null &'
        if user:
            p = ok(self.sudo(run_cmd, user=user))
        else:
            p = ok(self.run(run_cmd))
        print(p.stdout)

    def kill_bg(self, pid='/tmp/python-rc.pid', signal='TERM', timeout=None):
        return self.sudo(f'''
        /bin/kill -{signal} -$(cat {pid})
        while /bin/kill -0 -$(cat {pid}); do
            sleep 1
        done
        ''', timeout=timeout)

    def python(self, script, *, timeout=None, python_path='python', user=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE):
        return python(script, timeout=timeout, python_path=python_path, user=user, run_shell=self._ssh_shell(), stdout=stdout, stderr=stderr)

    def python2(self, script, **kwargs):
        return python2(script, run_shell=self._ssh_shell(), **kwargs)

    def python3(self, script, **kwargs):
        return python3(script, run_shell=self._ssh_shell(), **kwargs)

    def run_detach_tmux(self, cmd: str, *, name='python-rc', log='/tmp/python-rc.log'):
        return self.run(f"tmux new -s {name} -d '{cmd}' \\; pipe-pane 'cat > {log}'")

    def kill_detach_tmux(self, name='python-rc'):
        return self.run(f"tmux kill-session -t {name}")

    def save_image(self, image, **kwargs):
        return self.provider.save_image(self, image, **kwargs)

    @retry(MachineNotReadyException)
    def wait_ssh(self):
        p = self.run('echo a')
        if p.returncode != 0:
            raise MachineNotReadyException(p.stderr)

    def firewalls(self):
        return self.provider.machine_firewalls(self)

    def ensure_user(self, username, *, sudo=True, pubkey=True):
        add_sudo = ''
        if sudo:
            add_sudo = f'echo "{username}  ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/{username}'
        add_pubkey = ''
        if username == 'root':
            ssh_path = '/root/.ssh'
        else:
            ssh_path = f'/home/{username}/.ssh'
        if pubkey is True:
            pubkey = run(
                f'ssh-keygen -y -f {self.ssh_key_path}').stdout.strip()
        if pubkey:
            add_pubkey = f'''sudo -u {username} mkdir -p {ssh_path}
            if ! $(grep -Fxq '{pubkey}' {ssh_path}/authorized_keys); then
                sudo -u {username} echo "{pubkey}" >> {ssh_path}/authorized_keys
            fi
            '''
        cmd = f'''
        useradd {username} --create-home --shell /bin/bash || true
        {add_sudo}
        {add_pubkey}
        '''
        p = self.sudo(cmd)
        return p

    def edit(self, path, content, append=False, user=None):
        if append:
            op = '>>'
        else:
            op = '>'
        cmd = f"""cat {op} {path} <<'c7a88caeb23f4ac0f377c59b703fb7f1091d0708'
{content}
c7a88caeb23f4ac0f377c59b703fb7f1091d0708"""
        if user:
            return self.sudo(cmd, user=user)
        else:
            return self.bash(cmd)

    def ensure_lines(self, path, lines, user=None):
        pass

    def read(self, path):
        pass

    def ensure_file(self):
        pass

    def ensure_dir(self, path, user=None, allow_write=True):
        cmd = f'mkdir -p {path}'
        if allow_write:
            cmd += f'\nchmod a+w {path}'
        if user:
            return self.sudo(cmd, user=user)
        else:
            return self.bash(cmd)
