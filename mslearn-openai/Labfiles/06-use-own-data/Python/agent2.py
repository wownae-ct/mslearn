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
        my_version = "4"

        openai_client = project_client.get_openai_client()

        # ▼▼▼ [추가] 멀티턴용: 직전 응답 id 보관 (첫 턴은 None)
        previous_id = None
        print("대화 시작 (종료하려면 exit 또는 quit 입력)\n")

        # ▼▼▼ [추가] 사용자 입력을 계속 받는 멀티턴 루프
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ("exit", "quit"):
                break
            if not user_input:
                continue

            # [변경] create() 인자를 dict로 구성 (previous_response_id를 조건부로 넣기 위함)
            kwargs = {
                "input": [{"role": "user", "content": user_input}],
                "extra_body": {"agent_reference": {"name": my_agent, "version": my_version, "type": "agent_reference"}},
            }

            # [추가] 두 번째 턴부터 직전 응답 id를 넘겨 맥락 유지
            if previous_id:
                kwargs["previous_response_id"] = previous_id

            response = openai_client.responses.create(**kwargs)

            # [추가] 다음 턴을 위해 이번 응답 id 저장
            previous_id = response.id

            print(f"Agent: {response.output_text}\n")
        # ▲▲▲ [추가 끝]

    except Exception as ex:
        print(ex)


if __name__ == '__main__':
    main()