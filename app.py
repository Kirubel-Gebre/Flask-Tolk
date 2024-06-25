from flask import Flask, jsonify, Response, request, make_response
# from flask_cors import CORS
# from starlette.middleware.cors import CORSMiddleware
# from fastapi.responses import StreamingResponse
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import translate_v2 as translate
# import azure.cognitiveservices.speech as speechsdk
from openai import OpenAI
import os
import io
import json
# import tempfile
import requests
from pydub import AudioSegment
from scipy.io.wavfile import read as read_wav
import audioread
import soundfile as sf
import numpy as np

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

app = Flask(__name__)
# CORS(app, origins=["https://www.ai-tolk.nl/", "http://localhost:3000/"])
client = OpenAI()

# origins = [
#     "https://www.ai-tolk.nl/"

# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
#     expose_headers=["*"],
# )

@app.route("/", methods=["POST"])
async def transcribe_and_translate_audio():
    print("helloo")
    form_data = request.form
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
        
        audio_file = request.files.get("audio", "hello")
    
        temp_audio_file = "temp_audio.ogg"
        converted_audio_file = "temp_audio.wav"
        with open(temp_audio_file, "wb") as f:
            f.write(audio_file.read())
            
        # sampling_rate, data = read_wav(converted_audio_file)
        # sampling_rate, data = read_wav(temp_audio_file)
        # print(sampling_rate, data)

        # audio_file = request.files.get('audio')
        # temp_audio_file = "/tmp/temp_audio.ogg"
        # converted_audio_file = "/tmp/temp_audio.wav"
        # with open(temp_audio_file, "wb") as f:
        #     f.write(await audio_file.read())

        try:
            audio = AudioSegment.from_file(temp_audio_file, format="ogg")
            audio.export(converted_audio_file, format="wav")
            
            # Read the converted WAV file
            data, samplerate = sf.read(converted_audio_file)
            print(f"Sample rate: {samplerate}, Data type: {data.dtype}")
        except Exception as e:
            print("Audio conversion failed:", str(e))
            raise

        
        

        with open(converted_audio_file, "rb") as audio_file:
        # with open(temp_audio_file, "rb") as audio_file:
            content = audio_file.read()
        # Prepare the RecognitionAudio and RecognitionConfig objects
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=48000,
            language_code="am-ET",
        )

        # Perform the transcription
        gc_client = speech.SpeechClient()
        response = gc_client.recognize(config=config, audio=audio)


        transcribed_text = ""
        # Print the transcription results
        for result in response.results:
            # print(result.alternatives[0].transcript)
            transcribed_text += result.alternatives[0].transcript
        
    else:
        audio_file = request.files.get("audio", "hello")
    
        temp_audio_file = "temp_audio.wav"
        with open(temp_audio_file, "wb") as f:
            f.write(audio_file.read())

        # Use Whisper for transcription
        transcribed_text = transcribe_whisper(temp_audio_file)

    if is_geez == "true" or target_language in ["Amharic", "Tigrinya"]:
        # Translate using Google Cloud Translation for Amharic or Tigrinya
        translated_text = translate_text(transcribed_text, target_language=voice_options[target_language], source_language=voice_options[source_language])
    else:
        # Use OpenAI chat completions for translation
        response = client.chat.completions.create(
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
        
        # Cleanup temporary audio file
        os.remove(temp_audio_file)

    # Synthesize translated text to audio using Azure TTS

    audio_bytes = synthesize_audio(translated_text, language=voice_options[target_language])

    

    # Prepare response data
    response_data = {
        "sourceLanguage": source_language,
        "targetLanguage": target_language,
        "transcribedText": transcribed_text,
        "translatedText": translated_text
    }
    json_data = json.dumps(response_data)

    # return json_data
    
    # Create the Flask response
    response = make_response(json_data + "\n")
    response.set_data(response.get_data() + audio_bytes)
    response.headers.set('Content-Type', 'application/json')
    response.headers.set('Audio-Type', 'audio/mpeg')  # Assuming the audio is in MP3 format
    
    return response
    # Return response with JSON and audio bytes
    # return Response(
    #     content=json_data.encode() + b'\n' + audio_bytes,
    #     media_type="application/octet-stream"
    # )

def transcribe_whisper(audio_file_path: str) -> str:
    """Transcribes audio using Whisper from OpenAI."""
    with open(audio_file_path, "rb") as audio:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio
        )

    return transcript.text

def translate_text(text: str, target_language: str, source_language: str) -> str:
    """Translates text using Google Cloud Translation."""
    translate_client = translate.Client()
    result = translate_client.translate(text, target_language=target_language, source_language=source_language)

    return result['translatedText']

def synthesize_audio(text: str, language: str) -> bytes:
    """Synthesizes speech audio using Azure Text-to-Speech."""
    subscription_key = "e13bd4b8a3ad44e986342a0f7fe2dabc"
    region = "westeurope"

    # API endpoint
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
        
    # SSML (Speech Synthesis Markup Language) template
    ssml_template = f"""
    <speak version='1.0' xml:lang='{language}'>
        <voice name='{voice}'>
            {{text}}
        </voice>
    </speak>
    """

    # Prepare the SSML
    ssml = ssml_template.format(text=text)

    # Set up the HTTP headers
    headers = {
        "Ocp-Apim-Subscription-Key": subscription_key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        "User-Agent": "YourAppName"
    }

    # Send the request to Azure
    response = requests.post(constructed_url, headers=headers, data=ssml.encode("utf-8"))
   

    if response.status_code == 200:
        # Convert the response content to an AudioSegment
        # audio = AudioSegment.from_file(io.BytesIO(response.content), format="mp3")
        
        # # Export as WAV to bytes
        # buffer = io.BytesIO()
        # audio.export(buffer, format="wav")
        # audio_bytes = buffer.getvalue()
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
    