from fastapi import FastAPI,Request,Header
import requests
from requests.auth import HTTPBasicAuth
from pydantic.v1 import BaseSettings
from pydantic import BaseModel
from typing import List
import hmac
import hashlib

class Settings(BaseSettings):
    jira_email: str
    jira_api_token: str
    jira_base_url: str = "https://ssn-team-j7z071w8.atlassian.net"
    project_key: str = "ECSA"

    class Config:
        env_file = ".env"

settings = Settings()
auth = HTTPBasicAuth(settings.jira_email, settings.jira_api_token)

app = FastAPI()

class SummaryOnly(BaseModel):
    summary: str
    description: str | None = None

class VersionNameOnly(BaseModel):
    name: str

class ComponentInfo(BaseModel):
    name: str
    description: str | None = None  # Some components may not have a description

def fetch_issue_summaries(issue_type: str) -> List[SummaryOnly]:
    url = f"{settings.jira_base_url}/rest/api/3/search"
    params = {
        "jql": f"project={settings.project_key} AND issuetype={issue_type}",
        "fields": "summary",
        "maxResults": "1000"
    }
    response = requests.get(url, auth=auth, params=params)
    issues = response.json().get("issues", [])
    return [SummaryOnly(summary=issue["fields"]["summary"],description=issue["fields"].get("description")) for issue in issues]

def fetch_versions() -> List[VersionNameOnly]:
    url = f"{settings.jira_base_url}/rest/api/3/project/{settings.project_key}/versions"
    response = requests.get(url, auth=auth)
    versions = response.json()
    return [VersionNameOnly(name=v["name"]) for v in versions]

@app.get("/projects")
def get_projects():
    url = f"{settings.jira_base_url}/rest/api/3/project"
    return requests.get(url, auth=auth).json()

@app.get("/epics", response_model=List[SummaryOnly])
def get_epics():
    return fetch_issue_summaries("Epic")

@app.get("/stories", response_model=List[SummaryOnly])
def get_stories():
    return fetch_issue_summaries("Story")

@app.get("/tasks", response_model=List[SummaryOnly])
def get_tasks():
    return fetch_issue_summaries("Task")

@app.get("/bugs", response_model=List[SummaryOnly])
def get_bugs():
    return fetch_issue_summaries("Bug")

@app.get("/versions", response_model=List[VersionNameOnly])
def get_versions():
    return fetch_versions()

@app.get("/components", response_model=List[ComponentInfo])
def get_components():
    url = f"{settings.jira_base_url}/rest/api/3/project/{settings.project_key}/components"
    response = requests.get(url, auth=auth)
    components = response.json()
    return [ComponentInfo(name=c["name"], description=c.get("description")) for c in components]


@app.get("/labels")
def get_labels():
    url = f"{settings.jira_base_url}/rest/api/3/search"
    params = {
        "jql": f"project={settings.project_key}",
        "fields": "labels",
        "maxResults": "1000"
    }
    return requests.get(url, auth=auth, params=params).json()

@app.get("/issues/component/{component_name}")
def get_issues_by_component(component_name: str):
    url = f"{settings.jira_base_url}/rest/api/3/search"
    params = {"jql": f"project={settings.project_key} AND component=\"{component_name}\""}
    return requests.get(url, auth=auth, params=params).json()

@app.get("/issues/label/{label_name}")
def get_issues_by_label(label_name: str):
    url = f"{settings.jira_base_url}/rest/api/3/search"
    params = {"jql": f"project={settings.project_key} AND labels=\"{label_name}\""}
    return requests.get(url, auth=auth, params=params).json()

@app.post("/webhook/github")
async def github_webhook(request: Request, x_hub_signature_256: str = Header(None)):
    secret = b"github_webhook_secret"  # must match GitHub webhook secret
    body = await request.body()

    # Verify the payload signature (for security)
    hashed = hmac.new(secret, body, hashlib.sha256).hexdigest()
    expected_signature = f"sha256={hashed}"

    if not hmac.compare_digest(expected_signature, x_hub_signature_256 or ""):
        return {"message": "Invalid signature"}

    payload = await request.json()
    print("Received GitHub Webhook:", payload)

    # Do something with the webhook data here

    return {"message": "Webhook received successfully"}