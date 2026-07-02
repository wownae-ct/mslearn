from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
import numpy as np
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수에서 값 읽어오기
endpoint = os.environ.get("YOUR_FORM_RECOGNIZER_ENDPOINT")
key = os.environ.get("YOUR_FORM_RECOGNIZER_KEY")

print("엔드포인트:", endpoint)
print("키 로드 성공 여부:", bool(key))


def format_bounding_box(bounding_box):
    if not bounding_box:
        return "N/A"
    reshaped_bounding_box = np.array(bounding_box).reshape(-1, 2)
    return ", ".join(["[{}, {}]".format(x, y) for x, y in reshaped_bounding_box])


# 💡 URL과 로컬 경로를 통합하여 처리하는 함수
def analyze_document(source):

    # 1. 입력값이 웹 주소(URL)인 경우
    if source.startswith("http://") or source.startswith("https://"):
        print(f"\n[인증] URL에서 문서 분석 중: {source}")
        request_body = AnalyzeDocumentRequest(url_source=source)

    # 2. 입력값이 로컬 파일 경로인 경우
    else:
        if not os.path.exists(source):
            print(f"오류: {source} 파일을 찾을 수 없습니다.")
            return

        print(f"\n[인증] 로컬 파일에서 문서 분석 중: {source}")
        with open(source, "rb") as f:
            file_bytes = f.read()
        request_body = AnalyzeDocumentRequest(bytes_source=file_bytes)

    # 클라이언트 초기화 및 분석 요청
    document_intelligence_client = DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    poller = document_intelligence_client.begin_analyze_document(
        "prebuilt-read", request_body
    )
    result = poller.result()

    # 결과 출력 부분 (기존과 동일)
    print("Document contains content: ", result.content)

    for idx, style in enumerate(result.styles):
        print(
            "Document contains {} content".format(
                "handwritten" if style.is_handwritten else "no handwritten"
            )
        )

    for page in result.pages:
        print("----Analyzing Read from page #{}----".format(page.page_number))
        print(
            "Page has width: {} and height: {}, measured with unit: {}".format(
                page.width, page.height, page.unit
            )
        )

        for line_idx, line in enumerate(page.lines):
            print(
                "...Line # {} has text content '{}' within bounding box '{}'".format(
                    line_idx, line.content, format_bounding_box(line.polygon)
                )
            )

    print("----------------------------------------")


if __name__ == "__main__":
    # 테스트 1: 기존 URL 방식 호출
    url_target = "https://raw.githubusercontent.com/Azure-Samples/cognitive-services-REST-api-samples/master/curl/form-recognizer/sample-layout.pdf"
    analyze_document(url_target)

    # 테스트 2: 로컬 파일 방식 호출 (본인의 파일명으로 변경하세요)
    local_target = "안전해라 머리머리 발표자료.pdf"
    analyze_document(local_target)
