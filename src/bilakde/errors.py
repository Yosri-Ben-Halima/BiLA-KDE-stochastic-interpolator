"""Expected failures expose evidence, never a partial reconstruction."""


class BridgeError(Exception):
    def __init__(self, status, reason, diagnostics=None):
        super().__init__(reason)
        self.status = status
        self.reason = reason
        self.diagnostics = {} if diagnostics is None else diagnostics


class BridgeInputError(BridgeError, ValueError):
    pass


class DensityFitError(BridgeError):
    pass


class SamplingError(BridgeError):
    pass


class ResourceLimitError(BridgeError):
    pass


class SummaryPrecisionError(BridgeError):
    pass
