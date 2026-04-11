from googleapiclient.discovery import build
from config import settings
import isodate
from typing import List, Dict, Any


class YoutubeSearch:
    def __init__(self):
        self.youtube = build('youtube', 'v3', developerKey=settings.YOUTUBE_API_KEY)

    def search_videos(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Busca videos de YouTube y retorna información detallada

        Args:
            query: Término de búsqueda
            max_results: Número máximo de resultados

        Returns:
            Lista de videos con título, URL, thumbnail, duración y vistas
        """
        # 1. Buscar videos
        search_request = self.youtube.search().list(
            q=query,
            part='snippet',
            maxResults=max_results,
            relevanceLanguage='es',
            type='video'  # Solo videos, no playlists ni canales
        )
        search_response = search_request.execute()

        # Extraer IDs de videos
        video_ids = [item['id']['videoId'] for item in search_response['items'] if item['id'].get('videoId', None)]

        if not video_ids:
            return []

        # 2. Obtener detalles (duración, vistas)
        videos_request = self.youtube.videos().list(
            part='contentDetails,statistics,snippet',
            id=','.join(video_ids)
        )
        videos_response = videos_request.execute()

        # 3. Formatear resultados
        results = []
        for video in videos_response['items']:
            video_id = video['id']
            snippet = video['snippet']
            content_details = video['contentDetails']
            statistics = video['statistics']

            # Parsear duración ISO 8601 a segundos
            duration_iso = content_details['duration']
            duration_seconds = int(isodate.parse_duration(duration_iso).total_seconds())

            results.append({
                'video_id': video_id,
                'url': f'https://www.youtube.com/watch?v={video_id}',
                'title': snippet['title'],
                'description': snippet['description'],
                'thumbnail': snippet['thumbnails']['high']['url'],  # Alta resolución
                'channel_title': snippet['channelTitle'],
                'published_at': snippet['publishedAt'],
                'duration': duration_seconds,
                'duration_formatted': self._format_duration(duration_seconds),
                'view_count': int(statistics.get('viewCount', 0)),
                'view_count_formatted': self._format_views(int(statistics.get('viewCount', 0)))
            })

        return results

    def _format_duration(self, seconds: int) -> str:
        """Formatea segundos a HH:MM:SS o MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def _format_views(self, views: int) -> str:
        """Formatea número de vistas (ej: 1.2M, 500K)"""
        if views >= 1_000_000:
            return f"{views / 1_000_000:.1f}M"
        elif views >= 1_000:
            return f"{views / 1_000:.1f}K"
        return str(views)


# Singleton instance
youtube_search = YoutubeSearch()