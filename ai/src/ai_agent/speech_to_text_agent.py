from openai import OpenAI
import os

class SpeechToTextAgent(OpenAI):
    """
    A class to handle speech-to-text operations using OpenAI's API.
    Inherits from OpenAI to utilize its methods and properties.
    """

    def __init__(self, api_key: str = None):
        """
        Initializes the SpeechToTextAgent with the provided API key.

        :param api_key: The API key for OpenAI.
        """
        super().__init__(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def transcribe(self, audio_file: str) -> str:
        """
        Transcribes the given audio file to text.

        :param audio_file: Path to the audio file to be transcribed.
        :return: The transcribed text.
        """
        print(audio_file)
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"The audio file {audio_file} does not exist.")
        
        file = open(audio_file, "rb")

        print(file)

        transcription  = self.audio.transcriptions.create(
            file=file,
            model="gpt-4o-transcribe",
            prompt="فایل صوتی کاربر راه به متن پارسی تبدیل کن.",
        )
        return transcription.text
    
