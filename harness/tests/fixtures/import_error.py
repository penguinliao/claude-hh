"""A file that will fail on import due to a missing module."""

import nonexistent_module_xyz_12345

def hello():
    return nonexistent_module_xyz_12345.greet()
