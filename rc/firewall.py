class Firewall:
    def __init__(self, *, provider, name, direction='in', action='allow', ports, srcs=['0.0.0.0/0'], dsts=['0.0.0.0/0']):
        self.provider = provider
        self.name = name
        self.direction = direction
        self.action = action
        self.ports = ports
        self.srcs = srcs
        self.dsts = dsts

    def __eq__(self, other):
        return (self.provider, self.name, self.direction, self.action, self.ports, self.srcs, self.dsts) == \
            (other.provider, other.name, other.action,
             other.ports, other.srcs, other.dsts)

    def __expr__(self):
        if 'direction' == 'in':
            return f'Firewall(provider={self.provider}, name={self.name}, direction={self.direction}, action={self.action}, ports={self.ports}, srcs={self.src})'
        else:
            return f'Firewall(provider={self.provider}, name={self.name}, direction={self.direction}, action={self.action}, ports={self.ports}, dsts={self.dsts})'

    def machines(self):
        return self.provider.firewall_machines(self)

    def delete(self):
        return self.provider.delete_firewall(self)

    def add_to_machine(self, machine):
        return self.provider.add_firewall(machine, self)

    def remove_from_machine(self, machine):
        return self.provider.remove_firewall(machine, self)
