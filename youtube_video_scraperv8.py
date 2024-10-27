from googleapiclient.discovery import build
import pandas as pd
import os
import json
from datetime import datetime
import time
from pytubefix import YouTube
from ultralytics import YOLO
import cv2
from tqdm import tqdm

class YouTubeResearchScraper:
    def __init__(self, api_key, base_dir="infant-video-data-scraper", download_dir="downloaded_videos", processed_dir="yolo_processed_videos"):
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.base_dir = base_dir
        self.data_dir = os.path.join(self.base_dir, 'youtube_research_data')
        self.download_dir = os.path.join(self.base_dir, download_dir)
        self.processed_dir = os.path.join(self.base_dir, processed_dir)
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        
        self.failed_queries = []
        self.failed_downloads = []
        self.processed_videos = []
        self.downloaded_video_ids = set()
        
        # Load YOLOv8 model (you can choose different models like 'yolov8n.pt', 'yolov8s.pt', etc.)
        self.model = YOLO('yolov8n.pt')  # Nano model for faster processing; adjust as needed

    def search_videos(self, query, max_results=50):
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
                if video_id in self.downloaded_video_ids:
                    continue  # Skip duplicates
                video_url = f"https://www.youtube.com/watch?v={video_id}"

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
        try:
            yt = YouTube(video_url)
            stream = yt.streams.filter(progressive=True, file_extension='mp4', res=resolution).first()
            if not stream:
                stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            
            if not stream:
                print(f"No suitable streams found for video: {title} ({video_id})")
                self.failed_downloads.append({
                    'video_id': video_id,
                    'video_url': video_url,
                    'error': 'No suitable streams found.'
                })
                return None

            safe_title = "".join([c if c.isalnum() or c in " ._-()" else "_" for c in title])
            filename = f"{safe_title} ({video_id}).mp4"
            file_path = os.path.join(self.download_dir, filename)

            print(f"Downloading video: {title} ({video_id})")
            stream.download(output_path=self.download_dir, filename=filename)
            print(f"Downloaded to: {file_path}")
            self.downloaded_video_ids.add(video_id)
            return file_path

        except Exception as e:
            print(f"Unexpected error for video {video_id}: {str(e)}")
            self.failed_downloads.append({
                'video_id': video_id,
                'video_url': video_url,
                'error': str(e)
            })
        return None

    def process_video_with_yolo(self, video_path, video_id):
        try:
            # Initialize video capture
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Failed to open video: {video_path}")
                return

            # Get video properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            processed_path = os.path.join(self.processed_dir, f"processed_{os.path.basename(video_path)}")
            out = cv2.VideoWriter(processed_path, fourcc, fps, (width, height))

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Perform object detection
                results = self.model.predict(frame, verbose=False)
                detections = results[0].boxes  # Assuming one image at a time

                # Find the bounding box for the baby
                baby_boxes = []
                for box in detections:
                    cls = int(box.cls)
                    if cls == 0:  # Assuming class 0 is 'person'; adjust based on your model's classes
                        baby_boxes.append(box.xyxy[0].cpu().numpy())

                if baby_boxes:
                    # Assuming the first detected person is the baby; adjust logic as needed
                    x1, y1, x2, y2 = baby_boxes[0]
                    # Optionally, expand the bounding box to include more context
                    cropped_frame = frame[int(y1):int(y2), int(x1):int(x2)]
                    out.write(cropped_frame)
                else:
                    # If no baby detected, write the original frame or skip
                    out.write(frame)

            cap.release()
            out.release()
            print(f"Processed video saved to: {processed_path}")
            self.processed_videos.append(processed_path)

        except Exception as e:
            print(f"Error processing video {video_id} with YOLO: {str(e)}")

    def save_to_csv(self, videos):
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
        if self.failed_queries:
            failed_path = os.path.join(self.data_dir, 'failed_queries.json')
            with open(failed_path, 'w') as f:
                json.dump(self.failed_queries, f, indent=4)
            print(f"\nFailed queries saved to: {failed_path}")

    def save_failed_downloads(self):
        if self.failed_downloads:
            failed_downloads_path = os.path.join(self.data_dir, 'failed_downloads.json')
            with open(failed_downloads_path, 'w') as f:
                json.dump(self.failed_downloads, f, indent=4)
            print(f"\nFailed downloads saved to: {failed_downloads_path}")

    def collect_research_data(self, queries, max_results_per_query=25, download=True, resolution="720p", target_total_videos=500):
        all_videos = []
        self.downloaded_video_ids = set()

        # Load existing downloaded video IDs to prevent duplicates across runs
        existing_csv_files = [f for f in os.listdir(self.data_dir) if f.endswith('.csv')]
        for csv_file in existing_csv_files:
            df_existing = pd.read_csv(os.path.join(self.data_dir, csv_file))
            existing_ids = df_existing['video_id'].tolist()
            self.downloaded_video_ids.update(existing_ids)

        for query in queries:
            if len(all_videos) >= target_total_videos:
                break
            print(f"\nProcessing query: {query}")
            videos = self.search_videos(query, max_results_per_query)
            for video in videos:
                if len(all_videos) >= target_total_videos:
                    break
                if video['video_id'] not in self.downloaded_video_ids:
                    all_videos.append(video)
                    self.downloaded_video_ids.add(video['video_id'])
            time.sleep(2)

        csv_path = self.save_to_csv(all_videos)
        if csv_path:
            print(f"\nData saved to: {csv_path}")

        if self.failed_queries:
            self.save_failed_queries()
            print(f"\nFailed to process {len(self.failed_queries)} queries/videos.")

        if download:
            print("\nStarting video downloads and processing...")
            for video in tqdm(all_videos, desc="Downloading Videos"):
                video_url = video['video_url']
                title = video['title']
                video_id = video['video_id']
                downloaded_path = self.download_video(video_url, title, video_id, resolution=resolution)
                if downloaded_path:
                    self.process_video_with_yolo(downloaded_path, video_id)
                time.sleep(1)

            if self.failed_downloads:
                self.save_failed_downloads()
                print(f"\nFailed to download {len(self.failed_downloads)} videos.")

        return all_videos

if __name__ == "__main__":
    import os

    API_KEY = "AIzaSyCXGB5mrsOkodw-_BaOIVNgMYvyx6iz9o0"
    if not API_KEY:
        raise ValueError("No API key provided. Set the YOUTUBE_DATA_API_KEY environment variable.")

    scraper = YouTubeResearchScraper(
        api_key=API_KEY, 
        base_dir="infant-video-data-scraper", 
        download_dir="downloaded_videos",
        processed_dir="yolo_processed_videos"  # Changed directory name
    )

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
        "baby joy moments",
        "Asian baby laughing compilation",
        "African baby smiling videos",
        "European baby giggles compilation",
        "Hispanic baby happy moments",
        "Middle Eastern baby reactions",
        "Indigenous baby joyful moments",
        "Latino baby smiling compilation",
        "Caucasian baby laughing videos",
        "Pacific Islander baby giggles compilation",
        "South Asian baby happy moments"
    ]

    video_data = scraper.collect_research_data(
        queries=research_queries,
        max_results_per_query=25,  # Increased to fetch more per query
        download=True,
        resolution="720p",
        target_total_videos=500  # Targeting 500 unique videos
    )