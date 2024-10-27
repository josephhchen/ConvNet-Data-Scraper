from googleapiclient.discovery import build
from pytube import YouTube
import pandas as pd
import os
import json
from datetime import datetime
import time
from urllib.error import HTTPError

class YouTubeResearchScraper:
    def __init__(self, api_key, base_dir="infant-video-data-scraper"):
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.base_dir = base_dir
        self.data_dir = os.path.join(self.base_dir, 'youtube_research_data')
        self.infant_videos_dir = os.path.join(self.base_dir, 'infant_videos')
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.infant_videos_dir, exist_ok=True)
        
        self.failed_downloads = []

    def search_videos(self, query, max_results=50):
        videos = []
        next_page_token = None
        
        while len(videos) < max_results:
            request = self.youtube.search().list(
                q=query,
                part='snippet',
                maxResults=min(50, max_results - len(videos)),
                pageToken=next_page_token,
                type='video'
            )
            response = request.execute()
            
            for item in response['items']:
                video_id = item['id']['videoId']
                
                video_stats = self.youtube.videos().list(
                    part='statistics,contentDetails',
                    id=video_id
                ).execute()
                
                if video_stats['items']:
                    stats = video_stats['items'][0]
                    video_data = {
                        'video_id': video_id,
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'published_at': item['snippet']['publishedAt'],
                        'channel_id': item['snippet']['channelId'],
                        'channel_title': item['snippet']['channelTitle'],
                        'view_count': stats['statistics'].get('viewCount', 0),
                        'like_count': stats['statistics'].get('likeCount', 0),
                        'comment_count': stats['statistics'].get('commentCount', 0),
                        'duration': stats['contentDetails']['duration'],
                        'query': query
                    }
                    videos.append(video_data)
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
            time.sleep(1)
            
        return videos
    
    def download_video(self, video_id, output_path=None, max_retries=3):
        if output_path is None:
            output_path = self.infant_videos_dir
        
        for attempt in range(max_retries):
            try:
                yt = YouTube(f'https://www.youtube.com/watch?v={video_id}')
                
                streams = yt.streams.filter(progressive=True, file_extension='mp4')
                if not streams:
                    print(f"No suitable streams found for video {video_id}")
                    self.failed_downloads.append({
                        'video_id': video_id,
                        'error': 'No suitable streams found'
                    })
                    return False

                # Select the best available stream for download
                stream = streams.first()
                if not stream:
                    print(f"Could not find a valid stream for video {video_id}")
                    return False
                
                sanitized_title = "".join(x for x in yt.title if x.isalnum() or x in (' ', '-', '_'))
                filename = f"{video_id}_{sanitized_title[:50]}.mp4"
                
                print(f"\nDownloading: {filename}")
                stream.download(output_path, filename=filename)
                
                metadata = {
                    'video_id': video_id,
                    'title': yt.title,
                    'author': yt.author,
                    'length': yt.length,
                    'views': yt.views,
                    'rating': yt.rating,
                    'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'stream_quality': stream.resolution if hasattr(stream, 'resolution') else 'unknown'
                }
                
                metadata_path = os.path.join(output_path, f"{video_id}_metadata.json")
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=4)
                
                print(f"Successfully downloaded: {filename}")
                return True

            except HTTPError as e:
                error_details = e.read().decode()  # Decode the response to get error details
                print(f"HTTP Error {e.code} on attempt {attempt + 1} for video {video_id}: {error_details}")
                if attempt == max_retries - 1:
                    self.failed_downloads.append({
                        'video_id': video_id,
                        'error': f'HTTP Error {e.code}: {error_details}'
                    })
            except Exception as e:
                print(f"Error on attempt {attempt + 1} for video {video_id}: {str(e)}")
                if attempt == max_retries - 1:
                    self.failed_downloads.append({
                        'video_id': video_id,
                        'error': str(e)
                    })
            
            time.sleep(2)
        
        return False

    def save_failed_downloads(self):
        if self.failed_downloads:
            failed_path = os.path.join(self.data_dir, 'failed_downloads.json')
            with open(failed_path, 'w') as f:
                json.dump(self.failed_downloads, f, indent=4)
            print(f"\nFailed downloads saved to: {failed_path}")

    def collect_research_data(self, queries, max_results_per_query=50, download_videos=False):
        all_videos = []
        
        for query in queries:
            print(f"\nProcessing query: {query}")
            videos = self.search_videos(query, max_results_per_query)
            all_videos.extend(videos)
            
            if download_videos:
                for video in videos:
                    print(f"\nAttempting to download: {video['title']}")
                    success = self.download_video(video['video_id'])
                    if not success:
                        print(f"Failed to download: {video['title']}")
                    time.sleep(2)
        
        csv_path = self.save_to_csv(all_videos)
        print(f"\nData saved to: {csv_path}")
        
        if self.failed_downloads:
            self.save_failed_downloads()
            print(f"\nFailed to download {len(self.failed_downloads)} videos.")
        
        return all_videos

if __name__ == "__main__":
    API_KEY = "AIzaSyCXGB5mrsOkodw-_BaOIVNgMYvyx6iz9o0"
    
    scraper = YouTubeResearchScraper(API_KEY, base_dir="infant-video-data-scraper")
    
    research_queries = [
        "baby smiling compilation",
        "baby laughing videos",
        "baby first smile captured",
        "baby facial expressions",
        "baby giggles compilation",
        "baby happy moments",
        "cute baby reactions",
        "baby emotional expressions",
        "infant smile reaction",
        "baby joy moments"
    ]
    
    video_data = scraper.collect_research_data(
        queries=research_queries,
        max_results_per_query=10,
        download_videos=True
    )
