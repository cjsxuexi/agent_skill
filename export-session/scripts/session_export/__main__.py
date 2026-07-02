# -*- coding: utf-8 -*-
"""``python -m session_export ...`` entry point."""
import sys

from .export import main

if __name__ == "__main__":
    sys.exit(main())
