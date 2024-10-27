from googleapiclient.discovery import build
import pandas as pd
import os
from datetime import datetime
import time

class YouTubeResearchScraper:
    def __init__(self, api_key, base_dir="infant-video-data-scraper"):
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.base_dir = base_dir
        self.data_dir = os.path.join(self.base_dir, 'youtube_research_data')
        
        os.makedirs(self.data_dir, exist_ok=True)
    
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
    
    def save_to_csv(self, videos):
        df = pd.DataFrame(videos)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'youtube_videos_{timestamp}.csv'
        csv_path = os.path.join(self.data_dir, csv_filename)
        df.to_csv(csv_path, index=False)
        return csv_path
    
    def collect_research_data(self, queries, max_results_per_query=50):
        all_videos = []
        
        for query in queries:
            print(f"\nProcessing query: {query}")
            videos = self.search_videos(query, max_results_per_query)
            all_videos.extend(videos)
            time.sleep(2)
        
        csv_path = self.save_to_csv(all_videos)
        print(f"\nData saved to: {csv_path}")
        
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
        max_results_per_query=10
    )
