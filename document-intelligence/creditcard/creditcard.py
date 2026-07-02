"""
This code sample shows Prebuilt Credit Card operations with the Azure AI Document Intelligence client library.
The async versions of the samples require Python 3.8 or later.

To learn more, please visit the documentation - Quickstart: Document Intelligence (formerly Form Recognizer) SDKs
https://learn.microsoft.com/azure/ai-services/document-intelligence/quickstarts/get-started-sdks-rest-api?pivots=programming-language-python
"""

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수에서 값 읽어오기
endpoint = os.environ.get("YOUR_FORM_RECOGNIZER_ENDPOINT")
key = os.environ.get("YOUR_FORM_RECOGNIZER_KEY")
filepath = "./creditcard.jpg"

print("엔드포인트:", endpoint)
print("키 로드 성공 여부:", bool(key))

document_intelligence_client = DocumentIntelligenceClient(
    endpoint=endpoint, credential=AzureKeyCredential(key)
)

with open(filepath, "rb") as f:
    poller = document_intelligence_client.begin_analyze_document(
        "prebuilt-creditCard", body=f
    )
credits_cards = poller.result()

for idx, document in enumerate(credits_cards.documents):
    print("--------Recognizing document #{}--------".format(idx + 1))

    doc_type = document.doc_type
    if doc_type:
        print("Document Type: {}".format(doc_type))

    card_holder_name = document.fields.get("CardHolderName")
    if card_holder_name:
        print(
            "Card Holder Name: {} has confidence: {}".format(
                card_holder_name.value_string, card_holder_name.confidence
            )
        )

    card_number = document.fields.get("CardNumber")
    if card_number:
        print(
            "Card Number: {} has confidence: {}".format(
                card_number.value_string, card_number.confidence
            )
        )

    card_verification_value = document.fields.get("CardVerificationValue")
    if card_verification_value:
        print(
            "Card Verification Value: {} has confidence: {}".format(
                card_verification_value.value_string, card_verification_value.confidence
            )
        )

    expiration_date = document.fields.get("ExpirationDate")
    if expiration_date:
        print(
            "Expiration Date: {} has confidence: {}".format(
                expiration_date.value_string, expiration_date.confidence
            )
        )

    issuing_bank = document.fields.get("IssuingBank")
    if issuing_bank:
        print(
            "Issuing Bank: {} has confidence: {}".format(
                issuing_bank.value_string, issuing_bank.confidence
            )
        )

    payment_network = document.fields.get("PaymentNetwork")
    if payment_network:
        print(
            "Payment Network: {} has confidence: {}".format(
                payment_network.value_string, payment_network.confidence
            )
        )

    customer_service_phone_numbers = document.fields.get("CustomerServicePhoneNumbers")
    if customer_service_phone_numbers:
        print("Customer Service Phone Numbers:")
        for phone_idx, phone in enumerate(customer_service_phone_numbers.value_array):
            print(
                "......Phone #{}: {} has confidence: {}".format(
                    phone_idx + 1, phone.value_phone_number, phone.confidence
                )
            )

    print("--------------------------------------")
