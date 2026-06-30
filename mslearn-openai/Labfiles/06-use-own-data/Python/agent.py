# Before running the sample:
#    pip install azure-ai-projects>=2.1.0

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

def main(): 
        
    try:
        load_dotenv()
        azure_oai_endpoint = os.getenv("AZURE_OAI_AGENT_ENDPOINT")
        
        project_client = AIProjectClient(
            endpoint=azure_oai_endpoint,
            credential=DefaultAzureCredential(),
        )

        my_agent = "it-support-agent"
        my_version = "3"

        openai_client = project_client.get_openai_client()

        # Reference the agent to get a response
        response = openai_client.responses.create(
            input=[{"role": "user", "content": "Tell me what you can help with."}],
            extra_body={"agent_reference": {"name": my_agent, "version": my_version, "type": "agent_reference"}},
        )

        print(f"Response output: {response.output_text}")
        
    except Exception as ex:
        print(ex)


if __name__ == '__main__': 
    main()
