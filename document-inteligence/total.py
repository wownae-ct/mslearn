import os

import numpy as np
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    DocumentAnalysisFeature,
)
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import ContainerClient
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수에서 값 읽어오기
endpoint = os.environ.get("YOUR_FORM_RECOGNIZER_ENDPOINT")
key = os.environ.get("YOUR_FORM_RECOGNIZER_KEY")
sas_token = os.environ.get("AZURE_CONTAINER_SAS_TOKEN")
blob_endpoint = os.environ.get("AZURE_BLOB_CONTAINER_URL")

print("Document-Intelligence 엔드포인트:", endpoint)
print("키 로드 성공 여부:", bool(key))
print("SAS 토큰 로드 성공 여부:", bool(sas_token))
print("블롭 스토리지 URL 로드 성공 여부:", bool(blob_endpoint))


def format_bounding_box(bounding_box):
    if not bounding_box:
        return "N/A"
    reshaped_bounding_box = np.array(bounding_box).reshape(-1, 2)
    return ", ".join(["[{}, {}]".format(x, y) for x, y in reshaped_bounding_box])


# --- [모델 1] Prebuilt-Invoice 분석 로직 ---
def analyze_invoice_model(client, form_url):
    poller = client.begin_analyze_document(
        "prebuilt-invoice", AnalyzeDocumentRequest(url_source=form_url)
    )
    invoices = poller.result()

    docs_list = getattr(invoices, "documents", [])
    for idx, invoice in enumerate(docs_list):
        print("--------Recognizing invoice #{}--------".format(idx + 1))

        # 기본 정보 필드 방어 코드
        for field_name, attr_type in [
            ("VendorName", "value_string"),
            ("VendorAddress", "value_address"),
            ("VendorAddressRecipient", "value_string"),
            ("CustomerName", "value_string"),
            ("CustomerId", "value_string"),
            ("CustomerAddress", "value_address"),
            ("CustomerAddressRecipient", "value_string"),
            ("InvoiceId", "value_string"),
            ("InvoiceDate", "value_date"),
            ("DueDate", "value_date"),
            ("PurchaseOrder", "value_string"),
            ("BillingAddress", "value_address"),
            ("BillingAddressRecipient", "value_string"),
            ("ShippingAddress", "value_address"),
            ("ShippingAddressRecipient", "value_string"),
        ]:
            field_obj = invoice.fields.get(field_name)
            if field_obj and getattr(field_obj, attr_type, None):
                print(
                    f"{field_name}: {getattr(field_obj, attr_type)} has confidence: {field_obj.confidence}"
                )

        # 통화(금액) 관련 메인 필드 예외 처리
        invoice_total = invoice.fields.get("InvoiceTotal")
        if invoice_total:
            total_val = getattr(invoice_total, "value_currency", None)
            total_final = (
                total_val.amount
                if total_val
                else getattr(invoice_total, "value_string", "")
            )
            if total_final:
                print(
                    "Invoice Total: {} has confidence: {}".format(
                        total_final, invoice_total.confidence
                    )
                )

        # 세부 품목(Items) 순회 및 데이터 보호 파싱
        print("Invoice items:")
        items_field = invoice.fields.get("Items")
        if items_field and getattr(items_field, "value_array", None):
            for item_idx, item in enumerate(items_field.value_array):
                print("...Item #{}".format(item_idx + 1))

                # 품목 내부 텍스트 속성 검사
                for item_key, item_attr in [
                    ("Description", "value_string"),
                    ("Quantity", "value_number"),
                    ("Unit", "value_number"),
                    ("ProductCode", "value_string"),
                    ("Date", "value_date"),
                ]:
                    item_sub = item.value_object.get(item_key)
                    if item_sub and getattr(item_sub, item_attr, None):
                        print(
                            f"......{item_key}: {getattr(item_sub, item_attr)} has confidence: {item_sub.confidence}"
                        )

                # 품목 내부 금액/통화 객체 속성 검사
                for item_curr_key in ["UnitPrice", "Tax", "Amount"]:
                    curr_obj = item.value_object.get(item_curr_key)
                    if curr_obj:
                        c_val = getattr(curr_obj, "value_currency", None)
                        c_final = (
                            c_val.amount
                            if c_val
                            else getattr(curr_obj, "value_string", "")
                        )
                        if c_final:
                            print(
                                f"......{item_curr_key}: {c_final} has confidence: {curr_obj.confidence}"
                            )

        # 하단부 추가 정산 및 서비스 요약 필드 전체 방어 코드 적용
        for footer_key in [
            "SubTotal",
            "TotalTax",
            "PreviousUnpaidBalance",
            "AmountDue",
        ]:
            footer_obj = invoice.fields.get(footer_key)
            if footer_obj:
                f_val = getattr(footer_obj, "value_currency", None)
                f_final = (
                    f_val.amount if f_val else getattr(footer_obj, "value_string", "")
                )
                if f_final:
                    print(
                        f"{footer_key}: {f_final} has confidence: {footer_obj.confidence}"
                    )

        for date_key in ["ServiceStartDate", "ServiceEndDate"]:
            date_obj = invoice.fields.get(date_key)
            if date_obj and getattr(date_obj, "value_date", None):
                print(
                    f"{date_key}: {date_obj.value_date} has confidence: {date_obj.confidence}"
                )

        for addr_key in ["ServiceAddress", "RemittanceAddress"]:
            addr_obj = invoice.fields.get(addr_key)
            if addr_obj and getattr(addr_obj, "value_address", None):
                print(
                    f"{addr_key}: {addr_obj.value_address} has confidence: {addr_obj.confidence}"
                )

        for rec_key in ["ServiceAddressRecipient", "RemittanceAddressRecipient"]:
            rec_obj = invoice.fields.get(rec_key)
            if rec_obj and getattr(rec_obj, "value_string", None):
                print(
                    f"{rec_key}: {rec_obj.value_string} has confidence: {rec_obj.confidence}"
                )


# --- [모델 2] Prebuilt-Read 분석 로직 ---
def analyze_read_model(client, form_url):
    poller = client.begin_analyze_document(
        "prebuilt-read", AnalyzeDocumentRequest(url_source=form_url)
    )
    result = poller.result()

    if getattr(result, "content", None):
        print("Document contains content: ", result.content[:150], "...(생략)")

    for idx, style in enumerate(getattr(result, "styles", [])):
        is_hw = getattr(style, "is_handwritten", False)
        print(
            "Document contains {} content".format(
                "handwritten" if is_hw else "no handwritten"
            )
        )

    for page in getattr(result, "pages", []):
        print("----Analyzing Read from page #{}----".format(page.page_number))
        print(
            "Page has width: {} and height: {}, measured with unit: {}".format(
                page.width, page.height, page.unit
            )
        )

        for line_idx, line in enumerate(getattr(page, "lines", [])):
            print(
                "...Line # {} has text content '{}' within bounding box '{}'".format(
                    line_idx,
                    getattr(line, "content", ""),
                    format_bounding_box(getattr(line, "polygon", None)),
                )
            )
        for word in getattr(page, "words", []):
            print(
                "...Word '{}' has a confidence of {}".format(
                    getattr(word, "content", ""), getattr(word, "confidence", 0)
                )
            )


# --- [모델 3] Prebuilt-Layout 분석 로직 (에러 해결 완료) ---
def analyze_document_model(client, form_url):
    # 🌟 최신 규격 prebuilt-layout 호출
    poller = client.begin_analyze_document(
        "prebuilt-layout", AnalyzeDocumentRequest(url_source=form_url)
    )
    result = poller.result()

    # 1. 일반 텍스트 문단(Paragraphs) 출력 방어 코드
    print("----Paragraphs found in document----")
    paragraphs = getattr(result, "paragraphs", [])
    if paragraphs:
        for p_idx, paragraph in enumerate(paragraphs):
            # 너무 길면 끊어서 출력
            content = getattr(paragraph, "content", "")
            if content:
                print(
                    f"[{paragraph.role if getattr(paragraph, 'role', None) else 'Text'}] {content[:100]}"
                )

    # 2. 표(Tables) 구조 출력 방어 코드
    print("----Tables found in document----")
    tables = getattr(result, "tables", [])
    if tables:
        for t_idx, table in enumerate(tables):
            print(
                f"  📊 Table #{t_idx + 1} ({table.row_count} rows, {table.column_count} columns)"
            )
            # 표 내부 셀(Cells) 데이터 파싱
            for cell in getattr(table, "cells", []):
                print(
                    f"    - Cell [{cell.row_index}, {cell.column_index}]: {getattr(cell, 'content', '')}"
                )
    else:
        print("추출된 표가 없습니다.")


# --- [모델 4] Prebuilt-IdDocument 분석 로직 ---
def analyze_id_model(client, form_url):
    poller = client.begin_analyze_document(
        "prebuilt-idDocument", AnalyzeDocumentRequest(url_source=form_url)
    )
    id_documents = poller.result()

    for idx, id_document in enumerate(getattr(id_documents, "documents", [])):
        print("--------Recognizing ID document #{}--------".format(idx + 1))
        for id_key, id_attr in [
            ("FirstName", "value_string"),
            ("LastName", "value_string"),
            ("DocumentNumber", "value_string"),
            ("DateOfBirth", "value_date"),
            ("DateOfExpiration", "value_date"),
            ("Sex", "content"),
            ("Address", "value_address"),
            ("CountryRegion", "value_string"),
        ]:
            id_obj = id_document.fields.get(id_key)
            if id_obj and getattr(id_obj, id_attr, None):
                print(
                    f"{id_key}: {getattr(id_obj, id_attr)} has confidence: {id_obj.confidence}"
                )


# --- [모델 5] Prebuilt-Layout 기반 Query Fields 전용 분석 로직 (에러 해결 완료) ---
def analyze_query_fields_model(client, form_url, query_fields):
    print("----Query Fields Extraction----")

    # 🌟 [필수 수정] 최신 SDK에서는 features에 QUERY_FIELDS를 선언하고 query_fields를 넘겨야 합니다.
    request_params = AnalyzeDocumentRequest(
        url_source=form_url,
        features=[DocumentAnalysisFeature.QUERY_FIELDS],
        query_fields=query_fields,
    )

    poller = client.begin_analyze_document("prebuilt-layout", request_params)
    result = poller.result()

    # 결과 데이터에서 추출된 정답 필드 안전하게 파싱 (방어 코드)
    docs_list = getattr(result, "documents", [])
    if docs_list:
        for idx, doc in enumerate(docs_list):
            for q_field in query_fields:
                # fields가 None일 경우를 대비해 get 안전장치 추가
                fields_dict = getattr(doc, "fields", {}) or {}
                field_data = fields_dict.get(q_field)
                if field_data and getattr(field_data, "content", None):
                    print(
                        "💬 질문: '{}' -> 🎯 답변: '{}' (신뢰도: {})".format(
                            q_field, field_data.content, field_data.confidence
                        )
                    )
    else:
        print("❌ 요청한 질의문(Query Fields)에 매칭되는 정답을 찾지 못했습니다.")


# --- 메인 컨트롤러 (자동 매칭 분기 및 조건부 쿼리 필드 진입) ---
def main():
    # 저장소 컨테이너 접근
    container_client = ContainerClient.from_container_url(
        f"{blob_endpoint}?{sas_token}"
    )
    document_intelligence_client = DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    print("\n📂 특정 컨테이너 내부 전수 조사를 시작합니다...")

    # 총 처리된 파일 개수를 세기 위한 카운터 변수
    total_files_processed = 0

    for blob in container_client.list_blobs():
        if blob.name.endswith("/"):
            continue

        total_files_processed += 1
        print("\n==================================================")
        print(f"📄 대상 파일 인지: {blob.name} (누적: {total_files_processed}개)")
        print("==================================================")

        # 직속 다운로드 가능 경로 생성
        formUrl = f"{blob_endpoint}/{blob.name}?{sas_token}"
        lower_name = blob.name.lower()

        # 파일명 외에 '확장자'를 미리 추출하여 안전한 분기 기준으로 삼습니다.
        _, ext = os.path.splitext(lower_name)

        # 🌟 [리팩토링 1] 쿼리 필드(모델 5)를 적용하고 싶은 타깃 키워드와 질문 세트를 매핑합니다.
        # 파일명이 항상 다를 수 있으므로, 특정 핵심 단어가 포함되어 있을 때 작동하도록 구성합니다.
        TARGET_QUERIES = {
            "계획": ["프로젝트 이름", "시작 날짜", "담당자", "최종 목적"],
            "target": ["문서 제목", "발행일", "수신자"],
            "보고서": ["보고서 제목", "작성자", "핵심 요약"],
        }

        # 현재 파일 이름에 쿼리 타깃 키워드가 매칭되는지 안전하게 검사합니다.
        active_questions = None
        for keyword, q_list in TARGET_QUERIES.items():
            if keyword in lower_name:
                active_questions = q_list
                break

        try:
            # 1. 인보이스/영수증 양식 분기
            if (
                "invoice" in lower_name
                or "bill" in lower_name
                or "영수증" in lower_name
            ):
                print("▶ [자동 인식] [모델 1] Invoice(인보이스) 모델을 가동합니다.")
                analyze_invoice_model(document_intelligence_client, formUrl)

            # 2. 신분증(이미지) 양식 분기
            elif (
                "license" in lower_name
                or "passport" in lower_name
                or "id_" in lower_name
                or (ext in [".png", ".jpg", ".jpeg"] and "plan" not in lower_name)
            ):
                print("▶ [자동 인식] [모델 4] ID Document(신분증) 모델을 가동합니다.")
                analyze_id_model(document_intelligence_client, formUrl)

            # 3. 🌟 [리팩토링 2] 조건부 쿼리 필드 라우팅
            # PDF이면서 + 상단 TARGET_QUERIES 명단에 이름 힌트가 걸렸을 때만 모델 5(Query Fields)로 진입합니다.
            elif ext == ".pdf" and active_questions is not None:
                print(
                    "▶ [자동 인식] [모델 5] Query Fields(질의응답 추출) 모델을 가동합니다."
                )
                analyze_query_fields_model(
                    document_intelligence_client, formUrl, query_fields=active_questions
                )

            # 4. 🌟 [리팩토링 3] 일반 문서 구조 분석 라우팅
            # 이름 힌트가 없는 일반 PDF 파일이나 양식 파일은 순수 표 구조 분석(Layout 모델)으로 안전하게 흐릅니다.
            elif "form" in lower_name or "layout" in lower_name or ext == ".pdf":
                print(
                    "▶ [자동 인식] [모델 3] Layout(순수 표 구조 분석) 모델을 가동합니다."
                )
                analyze_document_model(document_intelligence_client, formUrl)

            # 5. 그 외 기타 파일 처리 (기타 포맷 이미지 등)
            else:
                print("▶ [기본 매칭] [모델 2] Read(일반 텍스트/OCR) 모델을 가동합니다.")
                analyze_read_model(document_intelligence_client, formUrl)

            print("\n----------------------------------------")
        except Exception as e:
            print(
                f"❌ 파일 [{blob.name}] 분석 중 알 수 없는 형식 오류 발생 (스킵): {e}"
            )

    # 전체 루프가 종료된 후 최종 알림 출력
    print("\n==================================================")
    print(
        f"🎉 [SUCCESS] 모든 파일 처리가 끝났습니다. 총 {total_files_processed}개의 파일을 분석했습니다."
    )
    print("==================================================")


if __name__ == "__main__":
    # 메인 함수를 호출하여 프로그램을 시작합니다.
    main()
