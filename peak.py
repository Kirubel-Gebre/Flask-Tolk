from quart import Quart, jsonify, request, make_response
from quart_cors import cors
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import translate_v2 as translate
from openai import AsyncOpenAI
import os
import io
import json
import requests
from pydub import AudioSegment
from scipy.io.wavfile import read as read_wav
import soundfile as sf
import numpy as np

os.environ["FFPROBE_PATH"] = "/usr/local/bin/ffprobe"
AudioSegment.ffprobe = os.environ["FFPROBE_PATH"]

# Define voice options for Azure Text-to-Speech
voice_options = {
    "Afrikaans": "af-ZA",
    "Amharic": "am-ET",
    "Arabic": "ar-SA",
    "Bulgarian": "bg-BG",
    "Bangla": "bn-BD",
    "Catalan": "ca-ES",
    "Czech": "cs-CZ",
    "Danish": "da-DK",
    "German": "de-DE",
    "Greek": "el-GR",
    "English (Australia)": "en-AU",
    "English (United Kingdom)": "en-GB",
    "English (India)": "en-IN",
    "English (United States)": "en-US",
    "Spanish (Spain)": "es-ES",
    "Spanish (Mexico)": "es-MX",
    "Spanish (United States)": "es-US",
    "Estonian": "et-EE",
    "Basque": "eu-ES",
    "Persian": "fa-IR",
    "Finnish": "fi-FI",
    "Filipino": "fil-PH",
    "French (Canada)": "fr-CA",
    "French (France)": "fr-FR",
    "Irish": "ga-IE",
    "Gujarati": "gu-IN",
    "Hebrew": "he-IL",
    "Hindi": "hi-IN",
    "Croatian": "hr-HR",
    "Hungarian": "hu-HU",
    "Indonesian": "id-ID",
    "Italian": "it-IT",
    "Japanese": "ja-JP",
    "Kannada": "kn-IN",
    "Korean": "ko-KR",
    "Lithuanian": "lt-LT",
    "Latvian": "lv-LV",
    "Malayalam": "ml-IN",
    "Marathi": "mr-IN",
    "Dutch": "nl-NL",
    "Norwegian": "nb-NO",
    "Polish": "pl-PL",
    "Portuguese (Brazil)": "pt-BR",
    "Portuguese (Portugal)": "pt-PT",
    "Romanian": "ro-RO",
    "Russian": "ru-RU",
    "Slovak": "sk-SK",
    "Slovenian": "sl-SI",
    "Serbian": "sr-RS",
    "Swedish": "sv-SE",
    "Swahili": "sw-KE",
    "Tamil": "ta-IN",
    "Telugu": "te-IN",
    "Thai": "th-TH",
    "Tigrinya": "ti",
    "Turkish": "tr-TR",
    "Ukrainian": "uk-UA",
    "Urdu": "ur-PK",
    "Vietnamese": "vi-VN",
    "Chinese (Simplified)": "zh-CN",
    "Chinese (Traditional)": "zh-TW",
}

app = Quart(__name__)
app = cors(app)
client = AsyncOpenAI()

@app.route("/", methods=["POST"])
async def transcribe_and_translate_audio():
    print("helloo")
    form_data = await request.form
    print(form_data)
    is_geez = form_data.get('isGeez', "false")
    print(is_geez)

    input_language = form_data.get('inputLanguage', 'English (United States)')
    output_language = form_data.get('outputLanguage', 'Dutch')
    direction = form_data.get('direction', 'input-to-output')

    if direction == 'input-to-output':
        source_language = input_language
        target_language = output_language
    else:
        source_language = output_language
        target_language = input_language

    print(source_language)
    print(target_language)

    if is_geez == "true":
        transcribed_text = form_data.get('transcribedText', '')
        
        audio_file = await request.files['audio'].read()
        temp_audio_file = "temp_audio.ogg"
        converted_audio_file = "temp_audio.wav"
        with open(temp_audio_file, "wb") as f:
            f.write(audio_file)

        try:
            audio = AudioSegment.from_file(temp_audio_file, format="ogg")
            audio.export(converted_audio_file, format="wav")
            
            # Read the converted WAV file
            data, samplerate = sf.read(converted_audio_file)
            print(f"Sample rate: {samplerate}, Data type: {data.dtype}")
        except Exception as e:
            print("Audio conversion failed:", str(e))
            raise

        sampling_rate, data = read_wav(converted_audio_file)
        
        with open(converted_audio_file, "rb") as audio_file:
            content = audio_file.read()
            
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=48000,
            language_code="am-ET",
        )

        gc_client = speech.SpeechClient()
        response = gc_client.recognize(config=config, audio=audio)

        transcribed_text = ""
        for result in response.results:
            transcribed_text += result.alternatives[0].transcript
        
    else:
        audio_file = (await request.files)['audio'].read()
        # print(audio_file)
        temp_audio_file = "temp_audio.wav"
        with open(temp_audio_file, "wb") as f:
            f.write(audio_file)

        transcribed_text = await transcribe_whisper(temp_audio_file)

    if is_geez == "true" or target_language in ["Amharic", "Tigrinya"]:
        translated_text = translate_text(transcribed_text, target_language=voice_options[target_language], source_language=voice_options[source_language])
    else:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo-0301",
            messages=[
                {
                    "role": "system",
                    "content": f"Je bent een tolk voor de gebruiker. Vertaal de inkomende tekst van {source_language} naar fatsoenlijk en correct {target_language}.  Als je de taal niet herkent als {target_language}, moet je het gewoon zo laten. Niet MEER zeggen dan de vertaling, geen woorden toevoegen aan de output."
                },
                {
                    "role": "user",
                    "content": transcribed_text
                }
            ],
            max_tokens=2048,
            n=1,
            stop=None,
            temperature=0.5,
        )
        translated_text = response.choices[0].message.content
        
        os.remove(temp_audio_file)

    audio_bytes = synthesize_audio(translated_text, language=voice_options[target_language])

    response_data = {
        "sourceLanguage": source_language,
        "targetLanguage": target_language,
        "transcribedText": transcribed_text,
        "translatedText": translated_text
    }
    json_data = json.dumps(response_data)
    print(response_data)

    response = make_response(json_data + "\n")
    response.set_data(response.get_data() + audio_bytes)
    response.headers['Content-Type'] = 'application/json'
    response.headers['Audio-Type'] = 'audio/mpeg'
    
    return response

async def transcribe_whisper(audio_file_path: str) -> str:
    with open(audio_file_path, "rb") as audio:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio
        )

    return transcript.text

def translate_text(text: str, target_language: str, source_language: str) -> str:
    translate_client = translate.Client()
    result = translate_client.translate(text, target_language=target_language, source_language=source_language)
    return result['translatedText']

def synthesize_audio(text: str, language: str) -> bytes:
    subscription_key = "e13bd4b8a3ad44e986342a0f7fe2dabc"
    region = "westeurope"

    base_url = f"https://{region}.tts.speech.microsoft.com/"
    path = "cognitiveservices/v1"
    constructed_url = base_url + path
    
    if language == "ti":
        language = "am-ET"
    
    voices_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
    response = requests.get(voices_url, headers={"Ocp-Apim-Subscription-Key": subscription_key})
    if response.status_code == 200:
        voices = response.json()
        voice = [voice['ShortName'] for voice in voices if voice['Locale'] == language][0]
    else:
        print(f"Error fetching voices: {response.status_code}, {response.text}")
        voice = ""

    ssml_template = f"""
    <speak version='1.0' xml:lang='{language}'>
        <voice name='{voice}'>
            {{text}}
        </voice>
    </speak>
    """

    ssml = ssml_template.format(text=text)

    headers = {
        "Ocp-Apim-Subscription-Key": subscription_key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        "User-Agent": "YourAppName"
    }

    response = requests.post(constructed_url, headers=headers, data=ssml.encode("utf-8"))

    if response.status_code == 200:
        audio_bytes = response.content
        print(f"Audio generated successfully for: {text}")
        return audio_bytes
    else:
        print(f"Error: {response.status_code}")
        print(f"Reason: {response.reason}")
        print(response.text)
        return None

if __name__ == "__main__":
    app.run()
