import subprocess
from rc.exception import ExecException
import sys


def exec(cmd, *, input=None, timeout=60):
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE if input else None,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
        p.communicate(input=input, timeout=timeout)
        return p
    except:
        raise ExecException(sys.exc_info()[0])
