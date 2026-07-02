import os
import threading

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()


def recognize_from_microphone():
    # This example requires environment variables named "SPEECH_KEY" and "ENDPOINT"
    speech_translation_config = speechsdk.translation.SpeechTranslationConfig(
        subscription=os.environ.get("SPEECH_KEY"), endpoint=os.environ.get("ENDPOINT")
    )
    speech_translation_config.speech_recognition_language = "ko-KR"

    to_language = "en"
    speech_translation_config.add_target_language(to_language)

    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    translation_recognizer = speechsdk.translation.TranslationRecognizer(
        translation_config=speech_translation_config, audio_config=audio_config
    )

    # 종료 명령어로 인식되면 세션을 끝내도록 지정
    exit_command = "번역 기능 끝내줘"

    # 인식 결과를 저장할 data/ 폴더 및 파일 준비 (없으면 생성)
    os.makedirs("mslearn-ai-speech/data", exist_ok=True)
    result_path = os.path.join("mslearn-ai-speech/data", "translate_result.txt")

    # recognize_once_async 루프 대신, 이벤트 콜백 + threading.Event로
    # 연속 인식(start_continuous_recognition_async)을 제어합니다.
    # -> 매 턴마다 리스닝이 끊겼다 재시작되는 구조가 아니라,
    #    한 번 시작하면 계속 마이크를 듣고 있다가 발화가 끝날 때마다 콜백이 호출됩니다.
    done = threading.Event()

    def on_recognized(evt: speechsdk.translation.TranslationRecognitionEventArgs):
        result = evt.result

        if result.reason == speechsdk.ResultReason.TranslatedSpeech:
            recognized_text = result.text.strip()
            translated_text = result.translations[to_language]

            if not recognized_text:
                return  # 빈 인식 결과는 무시

            print(f"Recognized: {recognized_text}")
            print(f"Translated into '{to_language}': {translated_text}")

            # 종료 명령어가 인식되면 세션 종료 신호
            if exit_command in recognized_text:
                print("바이바이 👋")
                done.set()
                return

            # 원문과 번역을 탭으로 구분해 함께 저장
            with open(result_path, "a", encoding="utf-8") as f:
                f.write(recognized_text + "\t" + translated_text + "\n")

        elif result.reason == speechsdk.ResultReason.NoMatch:
            # 연속 인식 중에는 NoMatch가 정상적으로 자주 발생할 수 있음
            # (침묵 구간마다 호출됨) -> 굳이 매번 출력하지 않고 무시해도 무방
            pass

    def on_canceled(evt: speechsdk.translation.TranslationRecognitionCanceledEventArgs):
        print(f"Speech Recognition canceled: {evt.reason}")
        if evt.reason == speechsdk.CancellationReason.Error:
            print(f"Error details: {evt.error_details}")
            print("Did you set the speech resource key and endpoint values?")
        # 에러든 정상 종료든 세션을 끝냄
        done.set()

    def on_session_stopped(evt):
        done.set()

    # 콜백 등록
    translation_recognizer.recognized.connect(on_recognized)
    translation_recognizer.canceled.connect(on_canceled)
    translation_recognizer.session_stopped.connect(on_session_stopped)

    print('Speak into your microphone. ("번역 기능 끝내줘" 라고 말하면 종료됩니다.)')

    # 연속 인식 시작 (비동기) - 이 시점부터 마이크가 끊기지 않고 계속 듣습니다.
    translation_recognizer.start_continuous_recognition_async().get()

    # 종료 명령어를 듣거나 취소/에러가 발생할 때까지 대기
    done.wait()

    # 연속 인식 정지
    translation_recognizer.stop_continuous_recognition_async().get()


if __name__ == "__main__":
    recognize_from_microphone()