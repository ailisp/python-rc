from paramiko import SSHClient, AutoAddPolicy, RSAKey
from paramiko.ssh_exception import AuthenticationException, SSHException as ParamikoSSHException
from scp import SCPClient, SCPException
from collections import namedtuple
from rc.exception import UploadException, DownloadException, SSHException


ExecResult = namedtuple('ExecResult', ['stdout', 'stderr', 'returncode'])


class Machine:
    def __init__(self, *, provider, name, zone, ip, username, ssh_key_path):
        self.provider = provider
        self.name = name
        self.zone = zone
        self.ip = ip
        self.username = username
        self.ssh_key_path = ssh_key_path

    def status(self):
        return self.provider.status(self)

    def bootup(self):
        return self.provider.bootup(self)

    def shutdown(self):
        return self.provider.shutdown(self)

    def _connect(self):
        if self.ssh_client is None:
            priv_key = RSAKey.from_private_key(self.ssh_key_path)
            client = SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(AutoAddPolicy())
            client.connect(self.ip, username=self.username, pkey=priv_key)
            self.client = client

    def upload(self, *, local_path, machine_path):
        self._connect()
        scp = SCPClient(self.client.get_transport())
        try:
            scp.put(local_path,
                    recursive=True,
                    remote_path=machine_path)
        except SCPException:
            raise UploadException(SCPException.message)
        finally:
            scp.close()

    def download(self, *, machine_path, local_path):
        self._connect()
        scp = SCPClient(self.conn.get_transport())
        try:
            scp.get(machine_path, local_path=local_path,
                    recursive=True)
        except SCPException:
            raise DownloadException(SCPException.message)
        finally:
            scp.close()

    def exec(self, cmd, *, env=None, timeout=None):
        self._connect()
        if type(cmd) is list:
            cmd = " ".join(cmd.map(lambda c: "''" if c == '' else c))
        try:
            _, stdout, stderr = self.client.exec_command(
                cmd, environment=env, timeout=timeout)
        except ParamikoSSHException:
            raise SSHException(ParamikoSSHException.message)
        return ExecResult(stdout, stderr, stdout.channel.recv_exit_status())
