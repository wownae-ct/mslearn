import os

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv
from openai import AzureOpenAI

# ----------------------------------------------------------------------------
# 이 스크립트는 Azure OpenAI "On Your Data" 확장(extensions/chat/completions)을
# 쓰지 않습니다. 대신:
#   1) Azure AI Search SDK로 직접 검색해서 관련 chunk를 가져오고
#   2) 그 텍스트를 우리가 만든 프롬프트(user 메시지) 안에 명시적으로 박아넣고
#   3) 일반 chat.completions.create()로 호출합니다.
# 이렇게 하면 모델에게 정확히 어떤 컨텍스트가 전달되는지 100% 통제할 수 있고,
# system 메시지 토큰 제한(400) 같은 On Your Data 고유의 제약도 받지 않습니다.
# ----------------------------------------------------------------------------

TOP_K = 5          # 검색해서 가져올 chunk 개수
CONTENT_FIELD = "content"   # 인덱스에서 본문 텍스트가 들어있는 필드명
TITLE_FIELD = "title"       # 인덱스에서 제목/파일명이 들어있는 필드명


def search_documents(search_client: SearchClient, query: str, top_k: int = TOP_K):
    """Azure AI Search에서 query와 관련된 chunk를 top_k개 가져온다.
    semantic search가 인덱스에 설정돼 있으면 시도하고, 실패하면 기본(BM25) 검색으로 fallback."""
    try:
        results = search_client.search(
            search_text=query,
            query_type="semantic",
            semantic_configuration_name="default",  # 인덱스 생성 시 자동 부여된 이름과 다르면 에러 -> fallback
            top=top_k,
        )
        return list(results)
    except Exception:
        # semantic 설정 이름이 다르거나 semantic search가 비활성화된 경우 기본 검색으로 재시도
        results = search_client.search(search_text=query, top=top_k)
        return list(results)


def build_context_block(docs):
    """검색 결과를 번호 매긴 텍스트 블록으로 정리. 프롬프트에 그대로 삽입."""
    if not docs:
        return "(검색된 문서가 없습니다.)"

    blocks = []
    for i, d in enumerate(docs, start=1):
        title = d.get(TITLE_FIELD) or "(제목 없음)"
        content = d.get(CONTENT_FIELD) or ""
        blocks.append(f"[문서 {i}] (출처: {title})\n{content}")
    return "\n\n".join(blocks)


def main():
    try:
        load_dotenv()

        azure_oai_endpoint = os.getenv("AZURE_OAI_ENDPOINT")
        azure_oai_key = os.getenv("AZURE_OAI_KEY")
        azure_oai_deployment = os.getenv("AZURE_OAI_DEPLOYMENT")
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        azure_search_key = os.getenv("AZURE_SEARCH_KEY")
        azure_search_index = os.getenv("AZURE_SEARCH_INDEX")

        print(f"인덱스: {azure_search_index}")

        # 일반 Azure OpenAI 클라이언트 (extensions 경로 아님 — base_url 그대로 사용)
        client = AzureOpenAI(
            azure_endpoint=azure_oai_endpoint,
            api_key=azure_oai_key,
            api_version="2024-06-01",
        )

        search_client = SearchClient(
            endpoint=azure_search_endpoint,
            index_name=azure_search_index,
            credential=AzureKeyCredential(azure_search_key),
        )

        # 대화 기록 (RAG 컨텍스트는 매 턴 새로 검색해서 user 메시지에 동적으로 삽입하므로
        # 여기엔 순수 대화 내용만 누적한다)
        chat_history = []

        system_message = (
            "너는 사용자가 제공한 문서를 근거로만 답하는 질문응답 어시스턴트다. "
            "반드시 한국어로 답하라. "
            "아래 사용자 메시지에 포함된 '검색된 문서' 내용에 명시적으로 나온 사실만 사용해서 답하라. "
            "검색된 문서에 없는 내용은 절대 추가하지 마라. 너의 사전 지식(SAS, 보안, 네트워크 등에 대한 "
            "일반적인 지식)으로 빈 칸을 채우지 마라. "
            "검색된 문서만으로 답을 알 수 없으면 '제공된 문서에서 해당 정보를 찾을 수 없습니다.'라고만 답하라. "
            "답변 마지막에 어떤 [문서 N]을 근거로 사용했는지 번호로 표시하라."
        )

        while True:
            text = input('\nEnter a question:\n')
            if text.lower() in ("quit", "exit"):
                break

            # 1) 검색
            docs = search_documents(search_client, text, TOP_K)
            context_block = build_context_block(docs)

            # 2) 검색 결과를 user 메시지 안에 명시적으로 삽입한 프롬프트 구성
            user_prompt = (
                f"질문: {text}\n\n"
                f"검색된 문서:\n{context_block}\n\n"
                "위 검색된 문서 내용만 근거로 질문에 답하라."
            )

            messages = (
                [{"role": "system", "content": system_message}]
                + chat_history
                + [{"role": "user", "content": user_prompt}]
            )

            print("...검색 결과를 컨텍스트로 넣어 모델 호출 중...")

            response = client.chat.completions.create(
                model=azure_oai_deployment,
                temperature=0.2,
                max_tokens=1000,
                messages=messages,
            )

            answer = response.choices[0].message.content
            print("Response: " + answer + "\n")

            # 대화 기록에는 원래 질문/답변만 남긴다 (검색 컨텍스트 통째로 누적하면 토큰이 빠르게 불어남)
            chat_history.append({"role": "user", "content": text})
            chat_history.append({"role": "assistant", "content": answer})

            # 3) 실제로 검색되어 모델에 전달된 chunk 확인 (디버깅용)
            print("검색된 문서 (실제 모델에 전달된 컨텍스트):")
            if not docs:
                print("  (검색 결과 없음)")
            for i, d in enumerate(docs, start=1):
                title = d.get(TITLE_FIELD) or "(제목 없음)"
                content_snippet = (d.get(CONTENT_FIELD) or "")[:300].replace("\n", " ")
                score = d.get("@search.score")
                print(f"  [{i}] {title} (score={score})")
                print(f"      {content_snippet}")
                print()

    except Exception as ex:
        print(ex)


if __name__ == '__main__':
    main()