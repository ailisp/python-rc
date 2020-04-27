# python-rc
[![PyPI version](https://badge.fury.io/py/python-rc.svg)](https://pypi.org/project/python-rc/)

Python remote control library for programmatically control remote machines of mutliple cloud providers. Currently support gcloud, azure and digitalocean.

## Usage
python-rc consists of python-rc lib and python-rc cli.

### python-rc cli
```
rc <group name> command ...: execute command non interactively in group of machines
rc <group name>/name_pattern1,... command ...: execute command non interactively in group of machines, but only subset that match pattern 
rc <group name> @file: execute content of local file in group of machines
rc tmux <group name>: launch a tmux that ssh to every instance in group of machines, input to one machine will be replicate to the group
rc edit <group name>: create or edit machines in group
rc cat <group name>: show machines in group
rc ls: show defined groups
rc rm <group name>: delete group definition (does not delete machines)
rc rsync: parallel rsync
rc ssh-config: generate ~/.ssh/config that can be used with ssh machine_name, scp, rsync, mosh, etc.
```
In python-rc tmux, you can use `C-b a` to toggle input to all machines and input into single machine.

### python-rc lib
Import one of provider module: gcloud, digitalocean and azure to get or create a machine. Use machine methods to execute shell commands, execute background task, edit file, etc on the machine. Example:
```
from rc import gcloud
m = gcloud.get('instance1')
# run a single line command
p = m.run('ls')
print(p.stdout)

# run a multiline command
m.bash('''
cd workspace/proj
make -j 4
''')

# run a muliline commands as root
m.sudo('''
apt update
apt install -y jq
''')

# edit a file, as user `ubuntu`:
m.edit('~/a.txt', '''
file line1
file line2
''', user='ubuntu')

# run a server process in background
m.run_bg('''
cd workspace/someserver
npm i
npm run
''')

# run a python snippet on a server
p = m.python('''
import json
j = json.load(open('foo.json'))
print(j['key'])
''')

# Useful utility example:
# parallel run tasks on each machine
from rc import pmap
def task(machine, script_path):
    machine.bootup()
    machine.upload(f'~/local/path/{script_path}', f'~/remote/path/script_path}')
    machine.run(f'bash remote/path/{script_path}')

pmap(lambda i: task(machines[i], tasks[i]), range(n))
```

## Documentation
TODO. See `rc/test/` for example usages for now

## Test
To run gcloud part test, `gcloud` cli needs to be installed and logged in.
```
pipenv sync -d
pipenv run pytest -s
```
