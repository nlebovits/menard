"""Python version compatibility shims."""

import sys

# tomllib is built-in from Python 3.11+
# For Python 3.10, use the tomli backport
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

__all__ = ["tomllib"]
