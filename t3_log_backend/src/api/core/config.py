import os


# PUBLIC_INTERFACE
def get_env(name: str, default: str | None = None) -> str:
    """Get an environment variable or raise a clear error if missing.

    Args:
        name: Environment variable name.
        default: Optional default value.

    Returns:
        The environment variable value.

    Raises:
        RuntimeError: If the variable is missing and no default is provided.
    """
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            "Configure it in the container environment (.env) before running."
        )
    return value
