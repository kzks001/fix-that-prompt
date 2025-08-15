"""
OIDC client helpers using Authlib for AWS Cognito.

This module encapsulates the minimum functionality we need in Chainlit:
- Build the Cognito OpenID configuration/metadata URLs from env
- Fetch userinfo from Cognito using a Bearer access token
- Build hosted UI links (signup) from environment variables
- Basic email/username extraction policy
"""

import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from authlib.integrations.requests_client import OAuth2Session


def get_server_metadata_url() -> Optional[str]:
    """Compute the server metadata URL from environment variables.

    Expected env vars:
    - AWS_REGION
    - COGNITO_USER_POOL_ID
    """
    region = os.getenv("AWS_REGION", "ap-southeast-1").strip()
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID", "").strip()
    if not user_pool_id:
        return None
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"


def get_userinfo_endpoint() -> Optional[str]:
    """Resolve the userinfo endpoint from env overrides or standard Hosted UI base URL."""
    # Prefer explicit env if provided by CDK
    userinfo_url = os.getenv("OAUTH_COGNITO_USERINFO_URL")
    if userinfo_url:
        return userinfo_url.rstrip("/")

    # Fallback: derive from base URL
    base_url = os.getenv("OAUTH_COGNITO_BASE_URL")
    if base_url:
        return f"{base_url.rstrip('/')}/oauth2/userInfo"

    # Last resort: try via metadata discovery
    # We avoid a network call here to keep this function light; caller can provide
    # explicit URL via env for production.
    return None


def fetch_userinfo(access_token: str) -> Optional[Dict[str, Any]]:
    """Fetch userinfo from Cognito using the given access token.

    Args:
        access_token: OAuth2 access token (Bearer)

    Returns:
        The userinfo JSON dict or None if it cannot be fetched.
    """
    if not access_token:
        return None

    userinfo_endpoint = get_userinfo_endpoint()
    if not userinfo_endpoint:
        return None

    # Use Authlib's OAuth2Session to perform the authenticated request.
    client_id = os.getenv("OAUTH_COGNITO_CLIENT_ID") or os.getenv("COGNITO_CLIENT_ID")
    client_secret = os.getenv("OAUTH_COGNITO_CLIENT_SECRET", "")

    session = OAuth2Session(
        client_id=client_id,
        client_secret=client_secret,
        token={
            "access_token": access_token,
            "token_type": "Bearer",
        },
    )
    try:
        resp = session.get(userinfo_endpoint, timeout=10)
        if resp.ok:
            return resp.json()
    except Exception:
        pass
    return None


def is_configured() -> bool:
    """Check whether minimal OIDC configuration is present in env."""
    client_id = os.getenv("OAUTH_COGNITO_CLIENT_ID") or os.getenv("COGNITO_CLIENT_ID")
    base_url = os.getenv("OAUTH_COGNITO_BASE_URL")
    authorize_url = os.getenv("OAUTH_COGNITO_AUTHORIZE_URL")
    token_url = os.getenv("OAUTH_COGNITO_TOKEN_URL")
    # Either provide base URL or explicit endpoints
    has_endpoints = bool(base_url) or bool(authorize_url and token_url)
    return bool(client_id and has_endpoints)


def get_hosted_ui_base_url() -> Optional[str]:
    base_url = os.getenv("OAUTH_COGNITO_BASE_URL")
    if base_url:
        return base_url.rstrip("/")
    # Fallback to domain only
    domain = os.getenv("COGNITO_USER_POOL_DOMAIN")
    if domain:
        return domain if domain.startswith("http") else f"https://{domain}"
    return None


def build_signup_url(redirect_uri: str) -> Optional[str]:
    """Build the AWS Cognito Hosted UI signup URL."""
    base = get_hosted_ui_base_url()
    client_id = os.getenv("OAUTH_COGNITO_CLIENT_ID") or os.getenv("COGNITO_CLIENT_ID")
    scope = os.getenv("OAUTH_COGNITO_SCOPE", "openid email profile")
    if not base or not client_id or not redirect_uri:
        return None
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": scope,
        "redirect_uri": redirect_uri,
    }
    return f"{base}/signup?{urlencode(params)}"


def extract_singlife_username(email: str) -> Optional[str]:
    if not email:
        return None
    email = email.strip().lower()
    if email.endswith("@singlife.com"):
        return email.split("@", 1)[0]
    return None
