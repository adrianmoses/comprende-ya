import yt_dlp
import os
from config import settings

class YouTubeService:

    def __init__(self):
        self.temp_dir = settings.TEMP_DIR

    def download_audio(self, url: str) -> tuple[str, dict]:
        """
        Descarga audio de YouTube y vuelva path y metadata
        :param url:
        :return:
        """

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '64',
            }],
            'outtmpl': f'{settings.TEMP_DIR}/%(id)s.%(ext)s',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            # Obtener datos sin descargar
            info = ydl.extract_info(url, download=False)

            if info['duration'] > settings.MAX_VIDEO_DURATION:
                raise ValueError(f"Video muy largo: {info['duration']}s (max duración: {settings.MAX_VIDEO_DURATION})")

            ydl.download([url])

            audio_path = f"{self.temp_dir}/{info['id']}.mp3"

            metadata = {
                'video_id': info['id'],
                'title': info['title'],
                'duration': info['duration'],
                'description': info.get('description', ''),
            }

            return audio_path, metadata


youtube_service = YouTubeService()