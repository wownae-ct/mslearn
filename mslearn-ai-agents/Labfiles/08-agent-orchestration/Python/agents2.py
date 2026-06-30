# Add references
import asyncio
from typing import cast

from agent_framework import Message
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import SequentialBuilder
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

load_dotenv()

async def main():
    # Agent instructions
    summarizer_instructions="""
    Summarize the customer's feedback in one short sentence. Keep it neutral and concise.
    Example output:
    App crashes during photo upload.
    User praises dark mode feature.
    """

    classifier_instructions="""
    Classify the feedback as one of the following: Positive, Negative, or Feature request.
    """

    action_instructions="""
    Based on the summary and classification, suggest the next action in one short sentence.
    Example output:
    Escalate as a high-priority bug for the mobile team.
    Log as positive feedback to share with design and marketing.
    Log as enhancement request for product backlog.
    """

    # Create the chat client
    # FoundryChatClient reads FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL from the
    # environment (.env) automatically. If your .env still uses the old
    # AZURE_AI_PROJECT_ENDPOINT / AZURE_AI_MODEL_DEPLOYMENT_NAME names, either
    # rename them or pass project_endpoint=... and model=... explicitly here.
    credential = AzureCliCredential()
    # FoundryChatClient does NOT support the async context manager protocol
    # (no __aexit__), unlike the old AzureAIAgentClient. Just instantiate it
    # directly instead of using `async with`.
    chat_client = FoundryChatClient(credential=credential)

    # Create agents
    summarizer = chat_client.as_agent(
        instructions=summarizer_instructions,
        name="summarizer",
    )

    classifier = chat_client.as_agent(
        instructions=classifier_instructions,
        name="classifier",
    )

    action = chat_client.as_agent(
        instructions=action_instructions,
        name="action",
    )

    # Build sequential orchestration.
    # intermediate_output_from="all_other" makes every non-final agent
    # (summarizer, classifier) also surface its response as an "intermediate"
    # output. Without this, only the last agent (action) in the chain is
    # observable from outside the workflow.
    # (Verified against the installed package: SequentialBuilder.__init__ has
    # no `intermediate_outputs` bool -- it's `intermediate_output_from`,
    # accepting a list of participants or "all" / "all_other".)
    workflow = SequentialBuilder(
        participants=[summarizer, classifier, action],
        intermediate_output_from="all_other",
    ).build()

    async def run_feedback(feedback: str) -> None:
        """Run the summarizer -> classifier -> action pipeline once for a
        given feedback string, and print the resulting message thread."""
        result = await workflow.run(f"Customer feedback: {feedback}")
        agent_responses = result.get_intermediate_outputs() + result.get_outputs()

        # Build the full message thread to display: the original feedback
        # prompt first, followed by each agent's response in pipeline order
        # (summarizer -> classifier -> action).
        collected: list[Message] = [Message("user", [f"Customer feedback: {feedback}"])]
        for response in agent_responses:
            for msg in cast("list[Message]", response.messages):
                # Guard against an agent occasionally yielding the same
                # message twice in a row (observed with the action agent).
                if collected and collected[-1].text == msg.text:
                    continue
                collected.append(msg)

        for i, msg in enumerate(collected, start=1):
            name = msg.author_name or ("assistant" if msg.role == "assistant" else "user")
            print(f"{'-' * 60}\n{i:02d} [{name}]\n{msg.text}")

    # Initialize the current feedback.
    # This is the lab's built-in example -- running the script immediately
    # processes this and prints the result, with no input required first.
    feedback = """
    I use the dashboard every day to monitor metrics, and it works well overall. 
    But when I'm working late at night, the bright screen is really harsh on my eyes. 
    If you added a dark mode option, it would make the experience much more comfortable.
    """
    await run_feedback(feedback)

    # After the built-in example finishes, optionally keep going: prompt for
    # additional feedback to test, one at a time. Type 'quit' or 'exit' (or
    # leave it blank) to stop.
    print("\nYou can enter more feedback to process below. Type 'quit' to exit.\n")
    while True:
        more_feedback = input("Enter feedback:\n").strip()
        if not more_feedback or more_feedback.lower() in ("quit", "exit"):
            break

        print(f"\n{'=' * 60}")
        await run_feedback(more_feedback)


if __name__ == "__main__":
    asyncio.run(main())