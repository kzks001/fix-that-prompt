"""Authentication utilities for Fix That Prompt game."""

from .oidc_client import (
    build_signup_url,
    extract_singlife_username,
    fetch_userinfo,
    get_server_metadata_url,
    get_userinfo_endpoint,
    is_configured,
)

__all__ = [
    "build_signup_url",
    "extract_singlife_username",
    "fetch_userinfo",
    "get_server_metadata_url",
    "get_userinfo_endpoint",
    "is_configured",
]
