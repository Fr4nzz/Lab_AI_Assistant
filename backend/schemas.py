"""
JSON Schemas - Validation for AI responses.
"""


def validate_ai_response(response: dict) -> tuple[bool, str]:
    """
    Validates that the AI response has required fields.
    Returns: (is_valid, error_message)
    """
    if "message" not in response:
        return False, "Missing required field: message"

    if "status" not in response:
        return False, "Missing required field: status"

    valid_statuses = ["executing", "waiting_for_user", "completed", "error"]
    if response["status"] not in valid_statuses:
        return False, f"Invalid status: {response['status']}. Must be one of {valid_statuses}"

    if "tool_calls" in response:
        if not isinstance(response["tool_calls"], list):
            return False, "tool_calls must be an array"

        for i, call in enumerate(response["tool_calls"]):
            if "tool" not in call:
                return False, f"tool_calls[{i}] missing 'tool' field"
            if "parameters" not in call:
                return False, f"tool_calls[{i}] missing 'parameters' field"

    return True, ""
