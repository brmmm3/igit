"""iGit resources."""

import os

_icon_path = os.path.join(os.path.dirname(__file__), "app_64.png")
app_icon_path = _icon_path if os.path.exists(_icon_path) else None
