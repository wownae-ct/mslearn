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

        # 대화 기록을 루프 밖에서 한 번만 초기화 (system 메시지 포함)
        messages = [
                        {"role": "system", "content": (
                                 "한국어로만 답하라. "
                                 "아래 검색된 문서 내용에 명시적으로 나온 사실만 사용하라. "
                                 "SAS, 보안, 네트워크 등에 대한 너의 일반 지식(IP 제한, 모니터링 등)을 절대 추가하지 마라. "
                                 "문서에 없는 내용이면 '문서에서 찾을 수 없습니다'라고 답하라."
                                )}
                    ]

        # Configure your data source
        extension_config = dict(dataSources=[
            {
                "type": "AzureCognitiveSearch",
                "parameters": {
                    "endpoint": azure_search_endpoint,
                    "key": azure_search_key,
                    "indexName": azure_search_index,
                    "inScope": True,   # 디버깅용: 검색 실패해도 일반 지식으로 답하게
                    # "strictness": 2     # 기본값보다 낮춰서 약한 매칭도 통과시킴 (1~5, 기본 3)
                }
            }
        ])

        # 종료 조건이 있는 while 루프로 감싸서 매 턴마다 반복
        while True:

            text = input('\nEnter a question:\n')

            # 종료 입력 처리
            if text.lower() in ("quit", "exit"):
                break

            # 새 사용자 입력을 기존 messages 리스트에 append (덮어쓰지 않고 누적)
            messages.append({"role": "user", "content": text})

            # Send request to Azure OpenAI model
            print("...Sending the following request to Azure OpenAI endpoint...")
            print("Request: " + text + "\n")

            response = client.chat.completions.create(
                model=azure_oai_deployment,
                temperature=0.2,
                max_tokens=1000,
                messages=messages,
                extra_body=extension_config
            )

            # Print response
            print("Response: " + response.choices[0].message.content + "\n")

            # 모델 응답도 messages에 append해서 다음 턴에 기억하게 함
            messages.append({"role": "assistant", "content": response.choices[0].message.content})

            if show_citations:
                # Print citations
                print("Citations:")
                citations = response.choices[0].message.context["messages"][0]["content"]
                citation_json = json.loads(citations)

                if not citation_json.get("citations"):
                    print("  (검색된 citation이 없습니다 — 데이터 소스에서 관련 문서를 찾지 못했을 가능성이 있습니다.)")

                for i, c in enumerate(citation_json.get("citations", []), start=1):
                    title = c.get('title') or "(제목 없음)"
                    url = c.get('url') or "(URL 없음)"
                    # 실제 검색되어 모델에 전달된 chunk 본문 미리보기.
                    # 이 내용이 비어 있거나 질문과 무관하면 검색/청킹 단계 문제,
                    # 내용은 맞는데 답변이 이를 반영하지 않으면 생성 단계 문제로 구분할 수 있음.
                    content_snippet = (c.get('content') or "")[:300].replace("\n", " ")
                    print(f"  [{i}] Title: {title}")
                    print(f"      URL: {url}")
                    print(f"      내용 미리보기: {content_snippet}")
                    print()

    except Exception as ex:
        print(ex)


if __name__ == '__main__':
    main()