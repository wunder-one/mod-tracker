"""
Patreon OAuth Proof of Concept
-------------------------------
This script demonstrates the full Patreon OAuth flow for a desktop app:
1. Opens the browser to Patreon's login page
2. Listens locally for the OAuth callback
3. Exchanges the code for tokens
4. Uses the token to fetch the user's identity and campaign memberships

Requirements:
    pip install requests

Setup:
    Fill in CLIENT_ID, CLIENT_SECRET below with your values from:
    https://www.patreon.com/portal/registration/register-clients
"""

import json
import webbrowser
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------ #
#  Step 1 & 2 — Local HTTP listener that catches the OAuth callback   #
# ------------------------------------------------------------------ #

# We use this to pass the captured code out of the handler and back
# to the main flow. The handler runs in a separate context so we
# need a mutable container to share data through.
_callback_result = {}


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """
    Handles the single GET request Patreon sends back after the user
    logs in. Parses the 'code' param from the URL and stores it so
    the main flow can pick it up.
    """

    def do_GET(self):
        # self.path looks like: /patreon/callback?code=XXXX&state=YYYY
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            _callback_result["code"] = params["code"][0]
            response_body = b"<h2>Login successful! You can close this tab.</h2>"
        else:
            # Patreon sends 'error' param if the user denied access
            error = params.get("error", ["unknown"])[0]
            _callback_result["error"] = error
            response_body = b"<h2>Login failed or was cancelled. You can close this tab.</h2>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format, *args):
        # Suppress the default server log spam in the terminal
        pass


def wait_for_callback():
    """
    Starts the local server and blocks until exactly one request comes
    in (the OAuth callback). Returns whatever ended up in _callback_result.
    """
    server = HTTPServer(("localhost", 7842), OAuthCallbackHandler)
    # handle_request() waits for ONE request then returns, unlike
    # serve_forever() which would loop indefinitely.
    print("Waiting for Patreon login...")
    server.handle_request()
    server.server_close()
    return _callback_result


# ------------------------------------------------------------------ #
#  Step 3 — Exchange the code for tokens                              #
# ------------------------------------------------------------------ #

def exchange_code_for_tokens(code):
    """
    POSTs to Patreon's token endpoint with the one-time code and gets
    back an access token and refresh token.
    """
    response = requests.post(PATREON_TOKEN_URL, data={
        "code": code,
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    })
    response.raise_for_status()
    return response.json()


# ------------------------------------------------------------------ #
#  Step 4 — Use the token to call the Patreon API                     #
# ------------------------------------------------------------------ #

def fetch_user_identity(session):
    """
    Fetches the logged-in user's basic profile info.
    """
    response = session.get(f"{PATREON_API_BASE}/identity", params={
        "fields[user]": "full_name,email",
    })
    response.raise_for_status()
    return response.json()


def fetch_memberships(session):
    """
    Fetches all campaigns the user is a member of (including free tiers).
    Returns the raw API response which includes campaign relationships.
    """
    response = session.get(f"{PATREON_API_BASE}/identity", params={
        "include": "memberships.campaign",
        "fields[member]": "patron_status,currently_entitled_amount_cents",
        "fields[campaign]": "creation_name,url,vanity",
    })
    response.raise_for_status()
    return response.json()


def fetch_posts_for_campaign(session, campaign_id):
    """
    Fetches recent posts for a given campaign ID.
    """
    response = session.get(f"{PATREON_API_BASE}/campaigns/{campaign_id}/posts", params={
        "fields[post]": "title,url,published_at,is_public",
    })
    response.raise_for_status()
    return response.json()


# ------------------------------------------------------------------ #
#  Main flow                                                          #
# ------------------------------------------------------------------ #

def main():
    # Build the Patreon authorization URL and open it in the browser
    auth_url = (
        f"{PATREON_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPES.replace(' ', '%20')}"
    )
    print(f"Opening browser for Patreon login...")
    webbrowser.open(auth_url)

    # Wait for the user to log in and Patreon to redirect back
    result = wait_for_callback()

    if "error" in result:
        print(f"OAuth failed: {result['error']}")
        return

    code = result["code"]
    print(f"Got authorization code.")

    # Exchange the code for tokens
    tokens = exchange_code_for_tokens(code)
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    print(f"Got access token.")

    # Optionally save tokens for later (so user doesn't need to log in again)
    with open("tokens.json", "w") as f:
        json.dump(tokens, f, indent=2)
    print("Tokens saved to tokens.json")

    # Set up a requests Session with the auth header so we don't
    # have to repeat it on every call
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "BG3-mod-tracker",
    })

    # Fetch and display basic user info
    identity = fetch_user_identity(session)
    user = identity["data"]["attributes"]
    print(f"\nLogged in as: {user.get('full_name')} ({user.get('email')})")

    # Fetch memberships — these are the Patreon campaigns the user has joined
    memberships_data = fetch_memberships(session)

    # The 'included' array contains the related campaign objects
    included = memberships_data.get("included", [])
    campaigns = [item for item in included if item["type"] == "campaign"]

    if not campaigns:
        print("\nNo campaign memberships found.")
        return

    print(f"\nFound {len(campaigns)} campaign memberships:")
    for campaign in campaigns:
        attrs = campaign["attributes"]
        print(f"  - {attrs.get('vanity') or attrs.get('creation_name')} | {attrs.get('url')}")

    # For each campaign, fetch recent posts and display them
    # In the real app this is where you'd do fuzzy matching against
    # installed mod names from meta.lsx
    print("\nFetching posts for each campaign...")
    for campaign in campaigns:
        campaign_id = campaign["id"]
        name = campaign["attributes"].get("vanity") or campaign["attributes"].get("creation_name")
        print(f"\n  [{name}]")

        posts_data = fetch_posts_for_campaign(session, campaign_id)
        posts = posts_data.get("data", [])

        if not posts:
            print("    No posts found.")
            continue

        for post in posts[:5]:  # just show first 5 for brevity
            attrs = post["attributes"]
            print(f"    - {attrs.get('title')} | {attrs.get('published_at')} | {attrs.get('url')}")


if __name__ == "__main__":
    main()