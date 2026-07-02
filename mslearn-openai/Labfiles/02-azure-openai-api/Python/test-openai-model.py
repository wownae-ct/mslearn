import os

from dotenv import load_dotenv

# Add Azure OpenAI package
from openai import AzureOpenAI


def main():

    try:

        # 1. 환경변수 가져오기(.env)
        load_dotenv()
        azure_oai_endpoint = os.getenv("AZURE_OAI_ENDPOINT")
        azure_oai_key = os.getenv("AZURE_OAI_KEY")
        azure_oai_deployment = os.getenv("AZURE_OAI_DEPLOYMENT")

        # 2. Azure Open AI 초기화
        client = AzureOpenAI(
            azure_endpoint=azure_oai_endpoint,
            api_key=azure_oai_key,
            api_version="2025-01-01-preview"
        )

        # 3. 시스템 프롬프트 작성
        system_message = """당신은 친절한 AI 도우미입니다."""
        messages_array = [
            {"role": "system", "content": system_message},
        ]

        # 채팅 시작!
        while True:  # 반복문 시작
            input_text = input("Enter the prompt (or type 'quit' to exit): ")
            if input_text.lower() == "quit":
                break
            if len(input_text) == 0:
                print("Please enter a prompt.")
                continue

            if input_text.lower() == "flush":
                messages_array = [
                    {"role": "system", "content": system_message},]

                print("\nAnswer: 초기화 되었습니다. \n")
                continue

                # 챗봇 재호출
                response = client.chat.completions.create(
                    model=azure_oai_deployment,
                    temperature=0.7,
                    max_tokens=800,
                    messages=messages_array
                )
                # 6. 챗봇 메시지 추출
                generated_text = response.choices[0].message.content

                # 7. 멀티턴 대화를 위한 챗봇 응답 추출
                messages_array.append(
                    {"role": "assistant", "content": generated_text})

                # 8. 챗봇 메시지 출력
                print("\n=================================")
                print(f"\nAnswer: {generated_text} \n")
                print(messages_array[:])

            if len(input_text) != 0:
                print("\nSending request to Azure OpenAI endpoint...\n\n")

                # 4. 사용자가 입력한 말을 쌓기
                messages_array.append({"role": "user", "content": input_text})

                # 5. 챗봇 호출 (이제 그동안 쌓인 대화가 통째로 전달됩니다)
                response = client.chat.completions.create(
                    model=azure_oai_deployment,
                    temperature=0.7,
                    max_tokens=800,
                    messages=messages_array
                )

                # 6. 챗봇 메시지 추출
                generated_text = response.choices[0].message.content

                # 7. 멀티턴 대화를 위한 챗봇 응답 추출
                messages_array.append(
                    {"role": "assistant", "content": generated_text})

                # 8. 챗봇 메시지 출력
                print("\n=================================")
                print(f"\nAnswer: {generated_text} \n")

                # print(messages_array[:])  # 질문 및 응답 컨텍스트 리스트에 저장된 것 확인

    except Exception as ex:
        print(ex)


if __name__ == '__main__':
    main()