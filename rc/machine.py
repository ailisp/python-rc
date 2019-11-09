from rc.exception import UploadException, DownloadException, SSHException
from io import StringIO
from rc.util import run


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

    def upload(self, local_path, machine_path):
        p = run(['scp', '-o', 'StrictHostKeyChecking=no',
                 '-i', self.ssh_key_path, '-r', local_path, self.username+'@'+self.ip+':'+machine_path])
        if p.returncode != 0:
            raise UploadException(p.stderr)
        return p

    def download(self, *, machine_path, local_path):
        p = run(['scp', '-o', 'StrictHostKeyChecking=no',
                 '-i', self.ssh_key_path, '-r', self.username + '@' + self.ip + ':' + machine_path, local_path])
        if p.returncode != 0:
            raise DownloadException(p.stderr)
        return p

    def run(self, cmd, *, timeout=None, input=None):
        ssh_shell = ['ssh', '-o', 'StrictHostKeyChecking=no',
                     '-i', self.ssh_key_path, self.username + '@' + self.ip, '--']
        return run(cmd, shell=ssh_shell, timeout=timeout, input=input)
