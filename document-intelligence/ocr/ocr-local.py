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


# 💡 변경됨: 파일 경로를 매개변수로 받도록 수정
def analyze_read_local(local_file_path):

    # 💡 로컬 파일을 바이너리 데이터로 읽기
    with open(local_file_path, "rb") as f:
        file_bytes = f.read()

    document_intelligence_client = DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    # 💡 url_source 대신 bytes_source를 사용하여 로컬 데이터 전송
    poller = document_intelligence_client.begin_analyze_document(
        "prebuilt-read", AnalyzeDocumentRequest(bytes_source=file_bytes)
    )
    result = poller.result()

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
                    line_idx,
                    line.content,
                    format_bounding_box(line.polygon),
                )
            )

        for word in page.words:
            print(
                "...Word '{}' has a confidence of {}".format(
                    word.content, word.confidence
                )
            )

    print("----------------------------------------")


if __name__ == "__main__":
    # 💡 여기에 분석하고 싶은 로컬 파일명을 적어주세요 (상대경로 또는 절대경로)
    # 예: "my_document.pdf", "receipt.jpg", "image.png" 모두 가능합니다.
    #     sample_file = "image_ocr-test2.png"
    sample_file = "ocr-test3.png"

    if os.path.exists(sample_file):
        analyze_read_local(sample_file)
    else:
        print(f"오류: {sample_file} 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
