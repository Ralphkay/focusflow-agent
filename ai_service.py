# ai_service.py

import logging
import requests
import json
from openai import OpenAI, AuthenticationError, APIConnectionError
from urllib.parse import urljoin
from datetime import date
from typing import Dict, Any

# --- Internal App Imports ---
from database import get_db_session, db_lock
from client_models import Project, Task, AggregatedActivity, EmployeeDetails
from config import CONFIG

# from sync import _get_csrf_token_for_sync, sync_session # REMOVED: Not needed for this GET request

logger = logging.getLogger(__name__)

# Configure OpenAI API with the key from your config file
openai_client = OpenAI(api_key=CONFIG.get("OPENAI_API_KEY"))


def get_employee_tasks_from_central_server(employee_id: str) -> list:
    """
    Fetches tasks and projects assigned to the employee from the central server.
    """
    CENTRAL_DASHBOARD_URL = CONFIG.get("CENTRAL_DASHBOARD_URL")
    client_api_key = CONFIG.get("permanent_client_api_key")

    if not CENTRAL_DASHBOARD_URL or not client_api_key:
        logger.error("Central server URL or API key is not configured. Cannot fetch tasks.")
        return []

    api_url = urljoin(CENTRAL_DASHBOARD_URL, 'api/client/user_projects')

    # FIX: Use the correct header for the central server API
    headers = {
        'X-API-Key': client_api_key,
        # REMOVED: 'Content-Type' header as it's not needed for a GET request
    }

    try:
        # FIX: Use a standard requests.get since session management is not required for this call
        response = requests.get(api_url, headers=headers, timeout=20)

        logger.info(f"Central server response status code: {response.status_code}")
        logger.debug(f"Central server response body: {response.text}")

        response.raise_for_status()

        projects_data = response.json().get('projects', [])
        tasks_data = []

        # Extract tasks from projects for a flat list
        for project in projects_data:
            for task in project.get('tasks', []):
                # We only care about active tasks for the planner
                if task['status'] in ['To Do', 'In Progress']:
                    tasks_data.append({
                        'id': task['id'],
                        'title': task['name'],
                        'status': task['status'],
                        'due_date': task['due_date'],
                        'project_name': project['name'],
                        'project_id': project['id']
                    })
        logger.info(f"Successfully fetched {len(tasks_data)} tasks from central server.")
        return tasks_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching tasks from central server: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred in get_employee_tasks_from_central_server: {e}", exc_info=True)
        return []


def get_ai_response(user_message: str, task_id: int = None) -> Dict[str, Any]:
    """
    Provides a contextual AI response using the OpenAI API.
    Handles both structured JSON for task planning and conversational responses.
    """
    try:
        employee_id = CONFIG.get('employee_id')

        # Determine the AI's role and tone based on the request
        system_prompt = """
        You are the FocusFlow AI Assistant, a professional and concise productivity tool. Your primary goal is to help users plan and break down their work.

        When the user asks you to create a plan for a task, you must generate a structured JSON response that is easy to follow.
        Your response must strictly adhere to the following JSON schema:
        {
          "type": "task_activities",
          "activities": [
            {
              "task_name": "string",
              "due_date": "YYYY-MM-DD",
              "status": "string"
            }
          ]
        }

        The 'task_name' should be a concise plan item, 'due_date' should be the planned due date for the activity (which should match the parent task's due date if available), and 'status' should always be 'To Do'.
        The number of activities should be a minimum of 5 and a maximum of 8.
        Do not output any conversational text or explanation when generating the JSON response.

        If the user's message is a general question and not related to task planning, provide a brief, friendly, conversational response as a string.
        """

        task_context = ""
        is_planning_request = "plan" in user_message.lower() or "break down" in user_message.lower()

        if task_id:
            tasks = get_employee_tasks_from_central_server(employee_id)
            task = next((t for t in tasks if str(t['id']) == str(task_id)), None)

            if task:
                task_context = f"The user is focused on the task: '{task['title']}' from project '{task['project_name']}'. Its due date is {task['due_date'] or 'N/A'}. All new activities should inherit this due date."
            else:
                task_context = f"The user is asking about a task with ID {task_id} that could not be found. "
        else:
            task_context = "No specific task context provided by the user."

        full_prompt = f"{system_prompt}\n--- CONTEXT ---\n{task_context}\n--- USER QUERY ---\n{user_message}"

        # Call the OpenAI API
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": full_prompt},
                {"role": "user", "content": user_message}
            ]
        )

        ai_response_content = response.choices[0].message.content
        logger.info("Received AI response.")

        if is_planning_request:
            # For planning requests, we strictly expect JSON
            try:
                parsed_response = json.loads(ai_response_content)
                if isinstance(parsed_response, dict) and parsed_response.get("type") == "task_activities":
                    logger.info("Received valid structured JSON response.")
                    return parsed_response
                else:
                    logger.warning("Received JSON response that did not match the expected schema for a plan.")
                    return {'response': "Sorry, I couldn't generate a valid plan for that. Please try again."}
            except json.JSONDecodeError:
                logger.error("Failed to decode JSON from AI response.", exc_info=True)
                return {'response': "Sorry, I couldn't generate a valid plan. My response was malformed."}
        else:
            # For general queries, return the conversational response directly
            return {'response': ai_response_content}

    except AuthenticationError as e:
        logger.error(f"OpenAI Authentication Error: {e}", exc_info=True)
        return {'error': 'Authentication failed. Please check your OpenAI API key.'}
    except (APIConnectionError, requests.exceptions.RequestException) as e:
        logger.error(f"OpenAI API Connection Error: {e}", exc_info=True)
        return {'error': 'Could not connect to the OpenAI API. Please check your network connection.'}
    except Exception as e:
        logger.error(f"An unexpected error occurred while calling OpenAI API: {e}", exc_info=True)
        return {'error': 'An internal error occurred while processing your request.'}
