import os

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

def speak_from_console():
    # This example requires environment variables named "SPEECH_KEY" and "ENDPOINT"
    # Replace with your own subscription key and endpoint, the endpoint is like : "https://YourResourceName.cognitiveservices.azure.com"
    speech_config = speechsdk.SpeechConfig(subscription=os.environ.get('SPEECH_KEY'), endpoint=os.environ.get('ENDPOINT'))
    audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

    # The neural multilingual voice can speak different languages based on the input text.
    # speech_config.speech_synthesis_voice_name='en-US-Ava:DragonHDLatestNeural'
    speech_config.speech_synthesis_voice_name='en-US-Andrew:DragonHDLatestNeural'

    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    # 종료 명령어로 입력되면 루프를 빠져나가도록 지정
    exit_command = "음성합성 끝내줘"

    print('Enter some text that you want to speak. ("음성합성 끝내줘" 라고 입력하면 종료됩니다.)')

    # 무한 루프로 멀티턴 음성 합성 수행
    while True:
        print("Enter some text that you want to speak >")
        text = input()

        # 입력된 문장에 종료 명령어가 포함되면 인사 후 루프 종료
        if exit_command in text.strip():
            print("바이바이 👋")
            break

        speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()

        if speech_synthesis_result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("Speech synthesized for text [{}]".format(text))
        elif speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speech_synthesis_result.cancellation_details
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                if cancellation_details.error_details:
                    print("Error details: {}".format(cancellation_details.error_details))
                    print("Did you set the speech resource key and endpoint values?")
                break  # 취소/에러 발생 시에도 무한 루프 종료


speak_from_console()
