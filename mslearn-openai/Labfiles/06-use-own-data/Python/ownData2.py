import os
import json
from dotenv import load_dotenv

# Add OpenAI import
from openai import AzureOpenAI

def main(): 
        
    try:
        # Flag to show citations
        show_citations = True
        
        # Get configuration settings 
        load_dotenv()
        azure_oai_endpoint = os.getenv("AZURE_OAI_ENDPOINT")
        azure_oai_key = os.getenv("AZURE_OAI_KEY")
        azure_oai_deployment = os.getenv("AZURE_OAI_DEPLOYMENT")
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        azure_search_key = os.getenv("AZURE_SEARCH_KEY")
        azure_search_index = os.getenv("AZURE_SEARCH_INDEX")
        print(azure_search_index)
        
        # Initialize the Azure OpenAI client
        client = AzureOpenAI(
            base_url=f"{azure_oai_endpoint}/openai/deployments/{azure_oai_deployment}/extensions",
            api_key=azure_oai_key,
            api_version="2023-09-01-preview")
        

        # [추가1] 대화 기록을 루프 밖에서 한 번만 초기화 (system 메시지 포함)
        messages = [
            {"role": "system", "content": (
                                            "You are a helpful travel agent. The retrieved documents may be in English. "
                                            "Read them carefully, but always respond to the user in Korean (한국어), "
                                            "regardless of the language of the source documents or the user's question. "
                                            "**Always answer in Korean.**"
                                            )}
        ]
        
        # Configure your data source
        extension_config = dict(dataSources = [
            {
                "type": "AzureCognitiveSearch",
                "parameters": {
                    "endpoint": azure_search_endpoint,
                    "key": azure_search_key,
                    "indexName": azure_search_index
                    # "inScope": False,   # 디버깅용: 검색 실패해도 일반 지식으로 답하게
                    # "strictness": 2     # 기본값보다 낮춰서 약한 매칭도 통과시킴 (1~5, 기본 3)
                }
            }
        ])

        # [추가2] 종료 조건이 있는 while 루프로 감싸서 매 턴마다 반복
        while True:

            text = input('\nEnter a question:\n')

            # [추가3] 종료 입력 처리 (while 루프 안에서)
            if text.lower() in ("quit", "exit"):
                break

            # [추가4] 새 사용자 입력을 기존 messages 리스트에 append (덮어쓰지 않고 누적)
            messages.append({"role": "user", "content": text})

            # Send request to Azure OpenAI model
            print("...Sending the following request to Azure OpenAI endpoint...")
            print("Request: " + text + "\n")

            response = client.chat.completions.create(
                model = azure_oai_deployment,
                temperature = 0.5,
                max_tokens = 1000,
                messages = messages,   # [수정] 기존 messages = [{"role": "system", ...}, {"role": "user", ...}] 두 줄을 누적된 messages 변수로 교체
                extra_body = extension_config
            )

            # Print response
            print("Response: " + response.choices[0].message.content + "\n")

            # [추가5] 모델 응답도 messages에 append해서 다음 턴에 기억하게 함
            messages.append({"role": "assistant", "content": response.choices[0].message.content})

            if (show_citations):
                # Print citations
                print("Citations:")
                citations = response.choices[0].message.context["messages"][0]["content"]
                citation_json = json.loads(citations)
                for c in citation_json["citations"]:
                    print("  Title: " + c['title'] + "\n    URL: " + c['url'])

    except Exception as ex:
        print(ex)


if __name__ == '__main__': 
    main()