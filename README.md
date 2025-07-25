# FastAPI with Jira Integration

This project provides a FastAPI-based web service that integrates with Jira Cloud. It allows you to fetch Jira issues, versions, components, and labels, and trigger Jira ticket creation via webhooks (e.g., from GitHub). The service is configurable via environment variables and uses the Jira REST API.

## Features
- Fetch Jira projects, epics, stories, tasks, bugs, versions, components, and labels
- Filter issues by component or label
- Webhook endpoint to automate Jira ticket creation from GitHub events
- Webhook endpoint to receive Jira events

## Requirements
- Python 3.8+
- Jira Cloud account and API token

## Installation
1. Clone this repository:
   ```bash
   git clone <repo-url>
   cd fast_api_with_jira
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root with the following variables:
   ```env
   jira_email=your-email@example.com
   jira_api_token=your-jira-api-token
   jira_base_url=https://your-domain.atlassian.net
   project_key=YOUR_PROJECT_KEY
   ```

## Running the App
Start the FastAPI server with Uvicorn:
```bash
uvicorn main:app --reload
```
The API will be available at [http://localhost:8000](http://localhost:8000)

## API Endpoints
| Method | Endpoint                        | Description                                 |
|--------|----------------------------------|---------------------------------------------|
| GET    | /projects                       | List all Jira projects                      |
| GET    | /epics                          | List all epics in the project               |
| GET    | /stories                        | List all stories in the project             |
| GET    | /tasks                          | List all tasks in the project               |
| GET    | /bugs                           | List all bugs in the project                |
| GET    | /versions                       | List all versions in the project            |
| GET    | /components                     | List all components in the project          |
| GET    | /labels                         | List all labels in the project              |
| GET    | /issues/component/{component}   | List issues by component                    |
| GET    | /issues/label/{label}           | List issues by label                        |
| POST   | /webhook/github                 | GitHub webhook to trigger Jira ticket       |
| POST   | /webhook/jira                   | Jira webhook endpoint                       |

## Usage Example
Fetch all epics:
```bash
curl http://localhost:8000/epics
```

## License
MIT 