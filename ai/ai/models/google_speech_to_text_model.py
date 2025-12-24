import os
import io
from pydub import AudioSegment
import speech_recognition as sr


class GoogleSpeechToTextModel:
    """
    Speech-to-text using Google's Speech Recognition API via speech_recognition + pydub.
    Supports .webm, .mp3, .wav, etc., by converting in-memory to PCM WAV.
    """

    def __init__(self, language: str = 'fa-IR'):
        """
        :param language: Language code for recognition (default 'fa-IR' for Persian/Farsi)
        :param ffmpeg_path: Absolute path to ffmpeg executable
        :param ffprobe_path: Absolute path to ffprobe executable
        """
        self.language = language
        self.recognizer = sr.Recognizer()



    def transcribe(self, audio_file: str) -> str:
        """
        Transcribes the given audio file to text using Google Speech Recognition.
        Converts to WAV in memory to avoid format issues.
        """
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file does not exist: {audio_file}")

        # Double-check file is readable
        if os.path.getsize(audio_file) == 0:
            raise ValueError(f"Audio file is empty: {audio_file}")

        try:
            # Load audio with pydub (ffmpeg will handle format detection)
            audio_segment = AudioSegment.from_file(audio_file)
        except Exception as e:
            raise RuntimeError(f"Failed to read audio file with ffmpeg: {e}")

        # Export to WAV in-memory
        wav_buffer = io.BytesIO()
        audio_segment.export(wav_buffer, format="wav")
        wav_buffer.seek(0)

        # Feed to speech_recognition
        with sr.AudioFile(wav_buffer) as source:
            audio_data = self.recognizer.record(source)

        try:
            return self.recognizer.recognize_google(audio_data, language=self.language)
        except sr.UnknownValueError:
            raise ValueError("Google could not understand the audio")
        except sr.RequestError as e:
            raise ConnectionError(f"Could not connect to Google Speech Recognition service: {e}")
