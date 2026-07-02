import os

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

def recognize_from_microphone():
    # This example requires environment variables named "SPEECH_KEY" and "ENDPOINT"
    # Replace with your own subscription key and endpoint, the endpoint is like : "https://YourResourceName.cognitiveservices.azure.com"
    speech_config = speechsdk.SpeechConfig(
        subscription=os.environ.get("SPEECH_KEY"), endpoint=os.environ.get("ENDPOINT")
    )
    speech_config.speech_recognition_language = "ko-KR"
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    # audio_config = speechsdk.audio.AudioConfig(filename="record.m4a") # .wav만 되는 거 같음.
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config
    )

    # 종료 명령어로 인식되면 루프를 빠져나가도록 지정
    exit_command = "음성인식 끝내줘"

    # 인식 결과를 저장할 data/ 폴더 및 파일 준비 (없으면 생성)
    os.makedirs("mslearn-ai-speech/data", exist_ok=True)
    result_path = os.path.join("mslearn-ai-speech/data", "stt_result.txt")

    print('Speak into your microphone. ("음성인식 끝내줘" 라고 말하면 종료됩니다.)')

    # 무한 루프로 멀티턴 인식 수행
    while True:
        speech_recognition_result = speech_recognizer.recognize_once_async().get()
        if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print("Recognized: {}".format(speech_recognition_result.text))

            # 인식된 문장에 종료 명령어가 포함되면 인사 후 루프 종료
            recognized_text = speech_recognition_result.text.strip()
            if exit_command in recognized_text:
                print("바이바이 👋")
                break

            # 인식된 문장을 data/stt_result.txt 에 한 줄씩 이어서 저장
            with open(result_path, "a", encoding="utf-8") as f:
                f.write(recognized_text + "\n")

        elif speech_recognition_result.reason == speechsdk.ResultReason.NoMatch:
            print(
                "No speech could be recognized: {}".format(
                    speech_recognition_result.no_match_details
                )
            )
        elif speech_recognition_result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speech_recognition_result.cancellation_details
            print("Speech Recognition canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print("Error details: {}".format(cancellation_details.error_details))
                print("Did you set the speech resource key and endpoint values?")
            break  # 취소/에러 발생 시에도 무한 루프 종료


recognize_from_microphone()
