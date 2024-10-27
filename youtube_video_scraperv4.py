from googleapiclient.discovery import build
import pandas as pd
import os
import json
from datetime import datetime
import time
from pytube import YouTube
from pytube.exceptions import PytubeError

class YouTubeResearchScraper:
    def __init__(self, api_key, base_dir="infant-video-data-scraper", download_dir="downloaded_videos"):
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.base_dir = base_dir
        self.data_dir = os.path.join(self.base_dir, 'youtube_research_data')
        self.download_dir = os.path.join(self.base_dir, download_dir)
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)
        
        self.failed_queries = []
        self.failed_downloads = []

    def search_videos(self, query, max_results=50):
        """
        Search for videos based on the query and collect metadata.

        Args:
            query (str): The search query.
            max_results (int): Maximum number of results to retrieve.

        Returns:
            list: A list of dictionaries containing video metadata.
        """
        videos = []
        next_page_token = None

        while len(videos) < max_results:
            try:
                request = self.youtube.search().list(
                    q=query,
                    part='snippet',
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token,
                    type='video'
                )
                response = request.execute()
            except Exception as e:
                print(f"Error during search for query '{query}': {str(e)}")
                self.failed_queries.append({
                    'query': query,
                    'error': str(e)
                })
                break

            for item in response.get('items', []):
                video_id = item['id']['videoId']
                video_url = f"https://www.youtube.com/watch?v={video_id}"

                # Fetch video statistics and content details
                try:
                    video_stats = self.youtube.videos().list(
                        part='statistics,contentDetails',
                        id=video_id
                    ).execute()
                except Exception as e:
                    print(f"Error fetching details for video ID '{video_id}': {str(e)}")
                    self.failed_queries.append({
                        'video_id': video_id,
                        'error': str(e)
                    })
                    continue

                if video_stats.get('items'):
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
                        'duration': stats['contentDetails'].get('duration', 'N/A'),
                        'video_url': video_url,
                        'query': query
                    }
                    videos.append(video_data)

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
            time.sleep(1)  # To respect API rate limits

        return videos

    def download_video(self, video_url, title, video_id, resolution="720p"):
        """
        Download a YouTube video using pytube.

        Args:
            video_url (str): The URL of the YouTube video.
            title (str): The title of the video.
            video_id (str): The unique ID of the video.
            resolution (str): Desired resolution for the downloaded video.

        Returns:
            str: The path to the downloaded video file, or None if failed.
        """
        try:
            yt = YouTube(video_url)
            stream = yt.streams.filter(progressive=True, file_extension='mp4', res=resolution).first()
            if not stream:
                # If desired resolution not available, get the highest resolution
                stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            
            if not stream:
                print(f"No suitable streams found for video: {title} ({video_id})")
                self.failed_downloads.append({
                    'video_id': video_id,
                    'video_url': video_url,
                    'error': 'No suitable streams found.'
                })
                return None

            # Clean the title to create a valid filename
            safe_title = "".join([c if c.isalnum() or c in " ._-()" else "_" for c in title])
            filename = f"{safe_title} ({video_id}).mp4"
            file_path = os.path.join(self.download_dir, filename)

            print(f"Downloading video: {title} ({video_id})")
            stream.download(output_path=self.download_dir, filename=filename)
            print(f"Downloaded to: {file_path}")
            return file_path

        except PytubeError as e:
            print(f"Pytube error for video {video_id}: {str(e)}")
            self.failed_downloads.append({
                'video_id': video_id,
                'video_url': video_url,
                'error': str(e)
            })
        except Exception as e:
            print(f"Unexpected error for video {video_id}: {str(e)}")
            self.failed_downloads.append({
                'video_id': video_id,
                'video_url': video_url,
                'error': str(e)
            })
        return None

    def save_to_csv(self, videos):
        """
        Save the collected video metadata to a CSV file.

        Args:
            videos (list): A list of dictionaries containing video metadata.

        Returns:
            str: The path to the saved CSV file.
        """
        if not videos:
            print("No videos to save.")
            return None

        df = pd.DataFrame(videos)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'youtube_videos_{timestamp}.csv'
        csv_path = os.path.join(self.data_dir, csv_filename)
        df.to_csv(csv_path, index=False)
        return csv_path

    def save_failed_queries(self):
        """
        Save failed queries and errors to a JSON file.
        """
        if self.failed_queries:
            failed_path = os.path.join(self.data_dir, 'failed_queries.json')
            with open(failed_path, 'w') as f:
                json.dump(self.failed_queries, f, indent=4)
            print(f"\nFailed queries saved to: {failed_path}")

    def save_failed_downloads(self):
        """
        Save failed downloads and errors to a JSON file.
        """
        if self.failed_downloads:
            failed_downloads_path = os.path.join(self.data_dir, 'failed_downloads.json')
            with open(failed_downloads_path, 'w') as f:
                json.dump(self.failed_downloads, f, indent=4)
            print(f"\nFailed downloads saved to: {failed_downloads_path}")

    def collect_research_data(self, queries, max_results_per_query=50, download=True, resolution="720p"):
        """
        Collect research data based on a list of queries and optionally download videos.

        Args:
            queries (list): A list of search queries.
            max_results_per_query (int): Maximum number of results per query.
            download (bool): Whether to download the videos.
            resolution (str): Desired resolution for downloaded videos.

        Returns:
            list: A combined list of all collected video metadata.
        """
        all_videos = []

        for query in queries:
            print(f"\nProcessing query: {query}")
            videos = self.search_videos(query, max_results_per_query)
            all_videos.extend(videos)
            time.sleep(2)  # To respect API rate limits

        csv_path = self.save_to_csv(all_videos)
        if csv_path:
            print(f"\nData saved to: {csv_path}")

        if self.failed_queries:
            self.save_failed_queries()
            print(f"\nFailed to process {len(self.failed_queries)} queries/videos.")

        if download:
            print("\nStarting video downloads...")
            for video in all_videos:
                video_url = video['video_url']
                title = video['title']
                video_id = video['video_id']
                self.download_video(video_url, title, video_id, resolution=resolution)
                time.sleep(1)  # To avoid hitting download rate limits

            if self.failed_downloads:
                self.save_failed_downloads()
                print(f"\nFailed to download {len(self.failed_downloads)} videos.")

        return all_videos

if __name__ == "__main__":
    API_KEY = "AIzaSyCXGB5mrsOkodw-_BaOIVNgMYvyx6iz9o0"

    scraper = YouTubeResearchScraper(API_KEY, base_dir="infant-video-data-scraper", download_dir="downloaded_videos")

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
        download=True,         # Set to True to enable downloading
        resolution="720p"      # Desired resolution (e.g., "720p", "480p", etc.)
    )
