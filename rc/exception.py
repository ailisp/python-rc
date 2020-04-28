class RcException(Exception):
    pass


class MachineCreationException(RcException):
    pass


class MachineDeletionException(RcException):
    pass


class MachineBootupException(RcException):
    pass


class MachineShutdownException(RcException):
    pass


class UploadException(RcException):
    pass


class DownloadException(RcException):
    pass


class SSHException(RcException):
    pass


class MachineNotRunningException(RcException):
    pass


class RunException(RcException):
    pass


class MachineChangeTypeException(RcException):
    pass


class MachineNotReadyException(RcException):
    pass


class SaveImageException(RcException):
    pass


class DeleteImageException(RcException):
    pass


class FirewallRuleCreationException(RcException):
    pass


class FirewallRuleDeleteionException(RcException):
    pass


class DiskCreationException(RcException):
    pass


class DiskDeletionException(RcException):
    pass


class MachineAddDiskException(RcException):
    pass


class MachineRemoveDiskException(RcException):
    pass


class PmapException(RcException):
    pass
