import os
import threading

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

# 언어별 TTS 보이스 설정
VOICE_MAP = {
    "ko-KR": "ko-KR-SunHiNeural",
    "en-US": "en-US-AvaNeural",
}

# 인식 언어(source) -> 번역 대상 언어(target) 매핑
TARGET_LANGUAGE_MAP = {
    "ko-KR": "en",
    "en-US": "ko",
}

EXIT_COMMANDS = ["번역 기능 끝내줘", "Stop translation"]


def build_synthesizer(speech_key, endpoint, voice_name):
    """언어별 보이스를 쓰는 TTS synthesizer를 만듭니다."""
    tts_config = speechsdk.SpeechConfig(subscription=speech_key, endpoint=endpoint)
    tts_config.speech_synthesis_voice_name = voice_name
    audio_output = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
    return speechsdk.SpeechSynthesizer(speech_config=tts_config, audio_config=audio_output)


def speak_async(synthesizer, text):
    """
    별도 스레드에서 TTS만 재생합니다. 마이크 인식 상태는 건드리지 않습니다.
    (stop/start로 마이크를 껐다 켜는 방식은 재연결 타이밍이 불안정해서
     오히려 마이크가 안 먹는 문제를 일으켜 제거했습니다.)

    주의: 스피커와 마이크를 함께 쓰는 환경(이어폰 미사용)에서는
    TTS로 나온 소리를 마이크가 다시 인식해서 무한 루프처럼 보일 수 있습니다.
    이어폰 사용을 권장합니다.
    """
    try:
        speak_result = synthesizer.speak_text_async(text).get()
        # print(f"[DEBUG] TTS 결과: reason={speak_result.reason}")
        if speak_result.reason == speechsdk.ResultReason.Canceled:
            cancellation = speak_result.cancellation_details
            print(f"TTS canceled: {cancellation.reason}")
            if cancellation.reason == speechsdk.CancellationReason.Error:
                print(f"TTS error details: {cancellation.error_details}")
    except Exception as e:
        print(f"[ERROR] TTS 처리 중 예외 발생: {e!r}")


def two_way_interpreter():
    speech_key = os.environ.get("SPEECH_KEY")
    endpoint = os.environ.get("ENDPOINT")

    # --- STT + 번역 설정 ---
    # 고정된 speech_recognition_language 대신, 두 언어를 동시에 후보로 두고
    # 매 발화마다 어떤 언어로 말했는지 자동 감지하도록 설정
    speech_translation_config = speechsdk.translation.SpeechTranslationConfig(
        subscription=speech_key, endpoint=endpoint
    )
    # 두 언어 모두를 번역 대상으로 등록 (감지된 언어의 반대쪽으로 번역하기 위해)
    speech_translation_config.add_target_language("en")
    speech_translation_config.add_target_language("ko")

    # 기본값은 "AtStart" - 세션 시작 시 딱 한 번만 언어를 감지하고 이후 고정됨.
    # 대화 중 화자(언어)가 계속 바뀌는 양방향 통역 상황이므로 "Continuous"로 설정해서
    # 매 발화마다 언어를 다시 감지하도록 함
    speech_translation_config.set_property(
        property_id=speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode,
        value="Continuous",
    )

    auto_detect_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
        languages=["ko-KR", "en-US"]
    )

    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    translation_recognizer = speechsdk.translation.TranslationRecognizer(
        translation_config=speech_translation_config,
        audio_config=audio_config,
        auto_detect_source_language_config=auto_detect_config,
    )

    # --- 언어별 TTS synthesizer 미리 준비 ---
    synthesizers = {
        lang: build_synthesizer(speech_key, endpoint, voice)
        for lang, voice in VOICE_MAP.items()
    }

    # 결과 저장 경로
    os.makedirs("mslearn-ai-speech/data", exist_ok=True)
    result_path = os.path.join("mslearn-ai-speech/data", "interpret_result.txt")

    done = threading.Event()

    def on_recognized(evt: speechsdk.translation.TranslationRecognitionEventArgs):
        result = evt.result

        if result.reason != speechsdk.ResultReason.TranslatedSpeech:
            return  # NoMatch 등은 무시

        recognized_text = result.text.strip()
        if not recognized_text:
            return

        # 이번 발화가 어떤 언어로 감지됐는지 확인
        detected_lang = result.properties.get(
            speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult
        )
        # print(f"[DEBUG] detected_lang = {detected_lang!r}")  # 감지 결과 디버그 출력

        if detected_lang not in TARGET_LANGUAGE_MAP:
            print(f"알 수 없는 언어로 감지됨: {detected_lang}, 무시합니다.")
            return

        target_lang_code = TARGET_LANGUAGE_MAP[detected_lang]  # "en" 또는 "ko"
        translated_text = result.translations[target_lang_code]

        # 감지된 언어에 따라 화살표 방향 표시
        arrow = "🇰🇷→🇺🇸" if detected_lang == "ko-KR" else "🇺🇸→🇰🇷"
        print(f"{arrow} {recognized_text}  ==>  {translated_text}")

        # 종료 명령어 체크 (대소문자 무시하고 비교)
        if any(cmd.lower() in recognized_text.lower() for cmd in EXIT_COMMANDS):
            print("바이바이 👋")
            done.set()
            return

        # 원문 + 번역 저장
        with open(result_path, "a", encoding="utf-8") as f:
            f.write(f"[{detected_lang}] {recognized_text}\t[{target_lang_code}] {translated_text}\n")

        # 번역된 문장을, 번역 대상 언어에 맞는 보이스로 읽어줌
        target_voice_lang = "en-US" if target_lang_code == "en" else "ko-KR"
        synthesizer = synthesizers[target_voice_lang]
        # print(f"[DEBUG] TTS 시도: voice={target_voice_lang}, text={translated_text!r}")

        # recognized 콜백은 SDK 내부 이벤트 디스패치 스레드에서 실행되므로,
        # 여기서 speak_text_async(...).get()처럼 오래 블로킹하면 다음 인식이 밀릴 수 있어
        # 별도 스레드에서 TTS를 재생합니다. (마이크 상태는 건드리지 않음)
        threading.Thread(
            target=speak_async,
            args=(synthesizer, translated_text),
            daemon=True,
        ).start()

    def on_canceled(evt: speechsdk.translation.TranslationRecognitionCanceledEventArgs):
        print(f"Speech Recognition canceled: {evt.reason}")
        if evt.reason == speechsdk.CancellationReason.Error:
            print(f"Error details: {evt.error_details}")
            print("Did you set the speech resource key and endpoint values?")
        done.set()

    def on_session_stopped(evt):
        done.set()

    translation_recognizer.recognized.connect(on_recognized)
    translation_recognizer.canceled.connect(on_canceled)
    translation_recognizer.session_stopped.connect(on_session_stopped)

    print("실시간 통역을 시작합니다. 한국어 또는 영어로 말씀하세요.")
    print('종료하려면 "번역 기능 끝내줘" 또는 "Stop translation"이라고 말씀하세요.')

    translation_recognizer.start_continuous_recognition_async().get()
    done.wait()
    translation_recognizer.stop_continuous_recognition_async().get()


if __name__ == "__main__":
    two_way_interpreter()