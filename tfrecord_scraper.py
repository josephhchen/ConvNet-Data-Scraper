import os
import time
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from googleapiclient.discovery import build
from pytube import YouTube
from tqdm import tqdm
import cv2
from ultralytics import YOLO

API_KEY = 'AIzaSyCXGB5mrsOkodw-_BaOIVNgMYvyx6iz9o0'  # Replace with your actual API key
SEARCH_QUERY = 'baby smiling OR baby crawling OR baby laughing OR infant playing OR cute baby reactions'
MAX_RESULTS = 50
DOWNLOAD_DIR = 'videos'

# Thresholds for baby detection
BABY_MIN_SIZE_RATIO = 0.1
BABY_MAX_SIZE_RATIO = 0.6

def search_infant_videos(api_key, query, max_results):
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    # Initialize empty list for video IDs
    video_ids = []
    next_page_token = None
    
    # Keep fetching until we have enough results or no more pages
    while len(video_ids) < max_results:
        try:
            request = youtube.search().list(
                q=query,
                part='id,snippet',
                type='video',
                maxResults=min(50, max_results - len(video_ids)),
                pageToken=next_page_token
            )
            response = request.execute()
            
            # Extract video IDs
            for item in response.get('items', []):
                if item['id']['kind'] == 'youtube#video':
                    video_ids.append(item['id']['videoId'])
            
            # Check if there are more pages
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
                
        except Exception as e:
            print(f"Error in YouTube API search: {str(e)}")
            break
    
    print(f"Found {len(video_ids)} videos for query '{query}'")
    return video_ids

def download_single_video(args):
    video_id, download_dir = args
    url = f'https://www.youtube.com/watch?v={video_id}'
    output_path = os.path.join(download_dir, f"{video_id}.mp4")
    
    if os.path.exists(output_path):
        print(f"Video {video_id} already exists, skipping")
        return f"Video {video_id} already exists, skipping"
    
    try:
        yt = YouTube(url)
        
        # Skip age-restricted videos
        if yt.age_restricted:
            print(f"Video {video_id} is age-restricted.")
            return f"Video {video_id} is age-restricted"
        
        # Get the highest quality stream under 720p to avoid huge files
        stream = (yt.streams
                 .filter(progressive=True, file_extension='mp4')
                 .filter(lambda s: s.resolution and int(s.resolution[:-1]) <= 720)
                 .order_by('resolution')
                 .desc()
                 .first())
        
        if not stream:
            print(f"No suitable stream found for {video_id}")
            return f"No suitable stream found for {video_id}"
        
        # Download with a timeout
        stream.download(output_path=download_dir, filename=f"{video_id}.mp4")
        
        # Verify the download
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"Successfully downloaded video {video_id}")
            return f"Downloaded {video_id}"
        else:
            if os.path.exists(output_path):
                os.remove(output_path)
            print(f"Download failed for {video_id}: Empty file")
            return f"Download failed for {video_id}: Empty file"
            
    except Exception as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        print(f"Error downloading {video_id}: {str(e)}")
        return f"Error downloading {video_id}: {str(e)}"


def download_videos(video_ids, download_dir, max_workers=4):
    os.makedirs(download_dir, exist_ok=True)
    print(f"\nDownloading {len(video_ids)} videos using {max_workers} workers...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        args = [(video_id, download_dir) for video_id in video_ids]
        results = list(tqdm(executor.map(download_single_video, args), 
                          total=len(video_ids), 
                          desc="Downloading"))
    
    # Print summary
    successes = sum(1 for r in results if "Downloaded" in r)
    print(f"\nDownload Summary:")
    print(f"Successfully downloaded: {successes}")
    print(f"Failed or skipped: {len(video_ids) - successes}")
    
    return results

def is_baby_detected(box, frame_width, frame_height):
    box_width = box[2] - box[0]
    box_height = box[3] - box[1]
    box_size = (box_width * box_height) / (frame_width * frame_height)
    
    return BABY_MIN_SIZE_RATIO < box_size < BABY_MAX_SIZE_RATIO

def yolo_filter(video_path, model):
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"Failed to open {video_path}")
            return False
        
        # Sample multiple frames
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames_to_check = min(5, frame_count)  # Check up to 5 frames
        
        for _ in range(frames_to_check):
            frame_pos = int(_ * frame_count / frames_to_check)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            ret, frame = cap.read()
            
            if not ret:
                continue
                
            frame_height, frame_width, _ = frame.shape
            results = model(frame)
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        cls = int(box.cls.cpu().numpy())
                        if cls == 0:  # person class
                            x_min, y_min, x_max, y_max = box.xyxy[0].cpu().numpy()
                            if is_baby_detected([x_min, y_min, x_max, y_max], 
                                             frame_width, frame_height):
                                cap.release()
                                return True
                                
        cap.release()
        return False
        
    except Exception as e:
        print(f"Error processing {video_path}: {str(e)}")
        return False

def filter_videos_with_yolo(download_dir):
    model = YOLO('yolov8n.pt')
    video_files = list(Path(download_dir).glob('*.mp4'))
    print(f"\nFiltering {len(video_files)} videos with YOLO...")
    
    valid_videos = []
    for video_file in tqdm(video_files, desc="Filtering"):
        if yolo_filter(video_file, model):
            valid_videos.append(str(video_file))
        else:
            try:
                os.remove(video_file)
            except Exception as e:
                print(f"Error removing {video_file}: {str(e)}")
                
    print(f"Found {len(valid_videos)} valid videos after filtering.")
    return valid_videos

def main():
    print("Starting video processing...")
    start_time = time.time()
    
    # Step 1: Search for videos
    video_ids = search_infant_videos(API_KEY, SEARCH_QUERY, MAX_RESULTS)
    
    # Step 2: Download videos
    download_results = download_videos(
        video_ids, 
        DOWNLOAD_DIR, 
        max_workers=min(4, multiprocessing.cpu_count())
    )
    
    # Step 3: Filter videos
    valid_videos = filter_videos_with_yolo(DOWNLOAD_DIR)
    
    elapsed_time = time.time() - start_time
    print(f"\nTotal processing time: {elapsed_time/60:.2f} minutes")
    print(f"Valid videos saved in '{DOWNLOAD_DIR}' directory")
    
    return valid_videos

if __name__ == "__main__":
    main()
