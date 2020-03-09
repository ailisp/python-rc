from rc.exception import UploadException, DownloadException
from io import StringIO
from rc.util import run, run_stream, convert_list_command_to_str


class Machine:
    def __init__(self, *, provider, name, zone, ip, username, ssh_key_path):
        self.provider = provider
        self.name = name
        self.zone = zone
        self.ip = ip
        self.username = username
        self.ssh_key_path = ssh_key_path

    def __eq__(self, other):
        return (self.provider, self.zone, self.ip, self.username, self.ssh_key_path) == (other.provider, other.zone, other.ip, other.username, other.ssh_key_path)

    def __str__(self):
        return 'Machine(provider={provider}, name={name}, zone={zone}, ip={ip}, username={username}, ssh_key_path={ssh_key_path})'.format(
            provider=self.provider,
            name=self.name,
            zone=self.zone,
            ip=self.ip,
            username=self.username,
            ssh_key_path=self.ssh_key_path
        )

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

    def upload(self, local_path, machine_path):
        p = run(
            f'scp -o StrictHostKeyChecking=no -i {self.ssh_key_path} -r {local_path} {self.username}@{self.ip}:{machine_path}')
        if p.returncode != 0:
            raise UploadException(p.stderr)
        return p

    def download(self, machine_path, local_path):
        p = run(
            f'scp -o StrictHostKeyChecking=no -i {self.ssh_key_path} -r {self.username}@{self.ip}:{machine_path} {local_path}')
        if p.returncode != 0:
            raise DownloadException(p.stderr)
        return p

    def _ssh_shell(self):
        return ['ssh', '-o', 'StrictHostKeyChecking=no',
                *(['-i', self.ssh_key_path] if self.ssh_key_path else []), self.username + '@' + self.ip, '--']

    def run(self, cmd, *, timeout=None, input=None):
        return run(cmd, shell=self._ssh_shell(), timeout=timeout, input=input)

    def run_stream(self, cmd, input=None):
        return run_stream(cmd, shell=self._ssh_shell(), input=input)

    def run_detach_tmux(self, cmd: str, *, name='python-rc', log='/tmp/python-rc.log'):
        return self.run(f"tmux new -s {name} -d '{cmd}' \\; pipe-pane 'cat > {log}'")

    def kill_detach_tmux(self, name='python-rc'):
        return self.run(f"tmux kill-session -t {name}")

    def save_image(self, image, **kwargs):
        return self.provider.save_image(self, image, **kwargs)
