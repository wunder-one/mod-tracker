from http.server import HTTPServer, BaseHTTPRequestHandler


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # self.path will be something like "/patreon/callback?code=XXXX&state=YYYY"
        print(self.path)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"You can close this tab now.")


from urllib.parse import urlparse, parse_qs

path = "/patreon/callback?code=abc123&state=xyz"
parsed = urlparse(path)
params = parse_qs(parsed.query)

code = params["code"][0]  # "abc123"



import webbrowser

auth_url = "https://www.patreon.com/oauth2/authorize?response_type=code&client_id=YOUR_ID&redirect_uri=http://localhost:7842/patreon/callback&scope=identity identity.memberships campaigns.posts"

webbrowser.open(auth_url)



import requests

response = requests.post("https://www.patreon.com/api/oauth2/token", data={
    "code": code,
    "grant_type": "authorization_code",
    "client_id": YOUR_CLIENT_ID,
    "client_secret": YOUR_CLIENT_SECRET,
    "redirect_uri": "http://localhost:7842/patreon/callback"
})

tokens = response.json()
access_token = tokens["access_token"]
refresh_token = tokens["refresh_token"]