from fastapi import FastAPI,Request,Header
import requests
from requests.auth import HTTPBasicAuth
from pydantic.v1 import BaseSettings
from pydantic import BaseModel
from typing import List
import hmac
import hashlib
import logging

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


# --- Reusable function to call the Jira Automation Service ---
def call_jira_automation_service(text_to_process: str, repo_name: str, assignee_email: str) -> dict:
    """
    Calls the external Jira ticket automation service.
    Returns a dictionary with the status of the call.
    """
    logging.info(f"Triggering Jira ticket generation for: {text_to_process}")

    jira_automation_url = "https://fastapi-jira-ticket-generator-632246617707.asia-south1.run.app/generate_ticket"

    automation_payload = {
        "commit_message": text_to_process,
        "repo": repo_name,
        "assignee_email": assignee_email
    }

    try:
        response = requests.post(jira_automation_url, json=automation_payload)
        response.raise_for_status()
        logging.info(f"Successfully triggered Jira ticket generation. Response: {response.json()}")
        return {
            "status": "success",
            "response": response.json()
        }
    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        if e.response is not None:
            error_detail = e.response.text
        logging.error(f"Failed to trigger Jira ticket generation. Error: {error_detail}")
        return {
            "status": "error",
            "detail": error_detail
        }


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
    secret = b"github_webhook_secret"  # Replace with your actual secret
    body = await request.body()

    # Signature verification
    hashed = hmac.new(secret, body, hashlib.sha256).hexdigest()
    expected_signature = f"sha256={hashed}"
    if not hmac.compare_digest(expected_signature, x_hub_signature_256 or ""):
        return {"message": "Invalid signature"}

    payload = await request.json()
    action = payload.get("action")

    # 1. Sub-Issue Added (custom event)
    if action == "sub_issue_added":
        sub_issue = payload.get("sub_issue", {})
        parent_issue = payload.get("parent_issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        return {
            "event": "sub_issue_added",
            "repository": repository.get("full_name"),
            "sub_issue": {
                "id": sub_issue.get("id"),
                "title": sub_issue.get("title"),
                "body": sub_issue.get("body"),
                "url": sub_issue.get("html_url"),
                "created_at": sub_issue.get("created_at"),
                "state": sub_issue.get("state"),
                "created_by": sub_issue.get("user", {}).get("login"),
            },
            "parent_issue": {
                "id": parent_issue.get("id"),
                "title": parent_issue.get("title"),
                "url": parent_issue.get("html_url"),
                "created_by": parent_issue.get("user", {}).get("login"),
            },
            "triggered_by": sender.get("login")
        }

    # 2. Issue Assigned
    if action == "assigned":
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        assignee = payload.get("assignee", {})

        return {
            "event": "issue_assigned",
            "repository": repository.get("full_name"),
            "issue_title": issue.get("title"),
            "issue_body": issue.get("body"),
            "issue_url": issue.get("html_url"),
            "assigned_to": assignee.get("login"),
            "assigned_by": sender.get("login"),
            "created_at": issue.get("created_at"),
            "state": issue.get("state")
        }

    # 3. Issue Opened
    if action == "opened" and "issue" in payload:
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        issue_title = issue.get("title")
        repo_full_name = repository.get("full_name")

        automation_status = {}
        if issue_title and repo_full_name:
            automation_status = call_jira_automation_service(
                text_to_process=issue_title,
                repo_name="ecommerce-app-krishna",
                assignee_email="srikrishnan2210608@ssn.edu.in"
            )

        return {
            "event": "issue_opened",
            "repository": repo_full_name,
            "title": issue_title,
            "url": issue.get("html_url"),
            "created_by": sender.get("login"),
            "jira_ticket_automation_status": automation_status
        }

    # 4. Push Event
    if "commits" in payload and "head_commit" in payload:
        head_commit = payload.get("head_commit", {})
        repository = payload.get("repository", {})
        pusher = payload.get("pusher", {})

        commit_message = head_commit.get("message")
        repo_full_name = repository.get("full_name")

        automation_status = {}
        if commit_message and repo_full_name:
            automation_status = call_jira_automation_service(
                text_to_process=commit_message,
                repo_name="ecommerce-app-krishna",
                assignee_email="srikrishnan2210608@ssn.edu.in"
            )

        return {
            "event": "push",
            "repository": repo_full_name,
            "message": commit_message,
            "url": head_commit.get("url"),
            "jira_ticket_automation_status": automation_status
        }

    # 5. Parent Issue Added (custom event)
    if action == "parent_issue_added":
        parent_issue = payload.get("parent_issue", {})
        sub_issue = payload.get("sub_issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        return {
            "event": "parent_issue_added",
            "repository": repository.get("full_name"),
            "parent_issue": {
                "id": parent_issue.get("id"),
                "title": parent_issue.get("title"),
                "url": parent_issue.get("html_url"),
                "created_by": parent_issue.get("user", {}).get("login"),
            },
            "sub_issue": {
                "id": sub_issue.get("id"),
                "title": sub_issue.get("title"),
                "body": sub_issue.get("body"),
                "url": sub_issue.get("html_url"),
                "created_at": sub_issue.get("created_at"),
                "state": sub_issue.get("state"),
                "created_by": sub_issue.get("user", {}).get("login"),
            },
            "triggered_by": sender.get("login")
        }

    # 6. Sub-Issue Opened (from your provided payload)
    if action == "opened" and payload.get("issue", {}).get("title", "").startswith("sub-issue"):
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        return {
            "event": "sub_issue_opened",
            "repository": repository.get("full_name"),
            "title": issue.get("title"),
            "body": issue.get("body"),
            "url": issue.get("html_url"),
            "created_by": sender.get("login"),
            "created_at": issue.get("created_at"),
            "state": issue.get("state"),
            "sub_issue_summary": issue.get("sub_issues_summary", {})
        }

    # 7. Pull-Request Assigned (from your provided payload)
    if action == "assigned" and "pull_request" in payload:
        pr = payload["pull_request"]
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        assignee = payload.get("assignee", {})

        return {
            "event": "pull_request_assigned",
            "repository": repository.get("full_name"),
            "pull_request_title": pr.get("title"),
            "pull_request_body": pr.get("body"),
            "pull_request_url": pr.get("html_url"),
            "assigned_to": assignee.get("login"),
            "assigned_by": sender.get("login"),
            "created_at": pr.get("created_at"),
            "state": pr.get("state")
        }

    # 8. Pull-Request Opened (from your provided payload)
    if action == "opened" and "pull_request" in payload:
        pr = payload["pull_request"]
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        return {
            "event": "pull_request_opened",
            "repository": repository.get("full_name"),
            "pull_request_title": pr.get("title"),
            "pull_request_body": pr.get("body"),
            "pull_request_url": pr.get("html_url"),
            "created_by": sender.get("login"),
            "created_at": pr.get("created_at"),
            "state": pr.get("state"),
            "base_branch": pr.get("base", {}).get("ref"),
            "head_branch": pr.get("head", {}).get("ref"),
        }

    # 9. Pull Request Labeled
    if action == "labeled" and "pull_request" in payload:
        pr = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        label = payload.get("label", {})

        return {
            "event": "pull_request_labeled",
            "repository": repository.get("full_name"),
            "pull_request_title": pr.get("title"),
            "pull_request_url": pr.get("html_url"),
            "label_added": label.get("name"),
            "labeled_by": sender.get("login"),
            "created_at": pr.get("created_at"),
            "state": pr.get("state"),
        }

    # Default
    return {"message": f"Unhandled action: {action}"}

@app.post("/webhook/jira")
async def jira_webhook(request: Request):
    body = await request.body()

    # Optional: Verify signature if you're sending one from Jira (you can also skip this part)
    # For now we assume shared secret validation is done manually here
    # For example: hash-based comparison if Jira adds support for HMAC (currently it doesn't)

    payload = await request.json()
    print(payload)
    webhook_event = payload.get("webhookEvent")

    issue = payload.get("issue", {})
    issue_key = issue.get("key")
    issue_fields = issue.get("fields", {})
    summary = issue_fields.get("summary")
    issue_type = issue_fields.get("issuetype", {}).get("name")
    status = issue_fields.get("status", {}).get("name")
    reporter = issue_fields.get("reporter", {}).get("displayName")

    return {
        "event": webhook_event,
        "issue_key": issue_key,
        "summary": summary,
        "type": issue_type,
        "status": status,
        "reported_by": reporter
    }
