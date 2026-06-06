from backend.features.agent.service import (
    AgentResponse,
    add_assistant_message,
    add_user_message,
    new_conversation,
)


def test_conversation_helpers_append_expected_roles():
    messages = new_conversation()
    messages = add_user_message(messages, "How many wells are there?")
    messages = add_assistant_message(messages, AgentResponse(text="There are 2,000 wells."))

    assert messages == [
        {"role": "user", "content": "How many wells are there?"},
        {"role": "assistant", "content": "There are 2,000 wells."},
    ]


def test_agent_response_defaults_are_ui_safe():
    response = AgentResponse()

    assert response.text == ""
    assert response.tool_calls == []
    assert response.kg_entities == []
    assert response.trace == []
