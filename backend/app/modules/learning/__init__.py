"""Learning loop package.

Keep this package initializer import-free so migration model registration can
load `app.modules.learning.models` without creating a circular dependency back
through `content_engine.models`. Import concrete services from their modules.
"""

__all__: list[str] = []
