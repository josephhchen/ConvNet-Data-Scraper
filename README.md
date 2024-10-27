# Algorithm for Scraping, Downloading, and Processing YouTube Baby Videos with YOLOv8 (CNN Arch)

## 1. Initialization

### Input:
- `api_key`: YouTube Data API key.
- `base_dir`: Base directory for storing data (default: "infant-video-data-scraper").
- `download_dir`: Directory for downloaded videos (default: "downloaded_videos").
- `processed_dir`: Directory for YOLO-processed videos (default: "yolo_processed_videos").

### Steps:

#### Set Up YouTube API Client:
- Initialize the YouTube Data API client using the provided `api_key`.

#### Create Necessary Directories:
- Construct paths for `youtube_research_data`, `downloaded_videos`, and `yolo_processed_videos` within `base_dir`.
- Create these directories if they do not already exist to organize data systematically.

#### Initialize Tracking Structures:
- `failed_queries`: List to record queries that encounter errors.
- `failed_downloads`: List to record downloads that fail.
- `processed_videos`: List to store paths of processed videos.
- `downloaded_video_ids`: Set to keep track of video IDs that have been downloaded, preventing duplicates.

#### Load YOLOv8 Model:
- Initialize the YOLOv8 model (`yolov8n.pt` for Nano variant) for object detection tasks.

## 2. Video Search and Retrieval

### Input:
- `queries`: List of search terms (e.g., "baby laughing compilation", "Asian baby smiling videos").
- `max_results_per_query`: Maximum number of videos to fetch per query (default: 25).
- `target_total_videos`: Total number of unique videos to download (default: 500).

### Steps:

#### Load Existing Video IDs:
- Scan existing CSV files in `youtube_research_data` to populate `downloaded_video_ids`, ensuring no re-downloading of previously fetched videos.

#### Iterate Through Each Query:
For each query in `queries`:

1. **Check Target Completion**:
   - If the number of accumulated videos (`all_videos`) reaches `target_total_videos`, terminate the search process.

2. **Execute Search**:
   - Use the YouTube Data API to search for videos matching the query, retrieving up to `max_results_per_query` results.
   - Handle API rate limits by implementing a sleep interval between requests.

#### Process Search Results:
For each video item in the search response:

- **Extract Video ID**:
  - Retrieve `video_id` from the search result.

- **Duplicate Check**:
  - If `video_id` is already in `downloaded_video_ids`, skip to the next video.

- **Fetch Video Details**:
  - Retrieve video statistics and content details (e.g., view count, duration) using the YouTube Data API.

- **Compile Video Metadata**:
  - Create a `video_data` dictionary containing metadata such as title, description, publication date, channel information, and video URL.

- **Accumulate Video Data**:
  - Append `video_data` to `all_videos` and add `video_id` to `downloaded_video_ids`.

## 3. Video Downloading

### Input:
- `all_videos`: List of video metadata dictionaries to be downloaded.
- `download`: Boolean flag to enable/disable downloading (default: True).
- `resolution`: Desired video resolution for download (default: "720p").

### Steps:

#### Initiate Download Process:
- If `download` is `True`, proceed with downloading videos.

#### Iterate Through Each Video:
For each video in `all_videos`:

- **Extract Video Information**:
  - Retrieve `video_url`, `title`, and `video_id` from the video.

- **Download Video**:
  - Utilize `pytubefix` to download the video in the specified resolution.
  - If the desired resolution isn't available, download the highest available resolution.
  - Sanitize the video title to create a valid filename.
  - Save the downloaded video in `download_dir` with the format: "sanitized_title (video_id).mp4".

- **Update Tracking**:
  - Add `video_id` to `downloaded_video_ids` upon successful download.

- **Handle Download Failures**:
  - If downloading fails, record the `video_id`, `video_url`, and error message in `failed_downloads`.

- **Progress Tracking**:
  - Utilize `tqdm` to display a progress bar, providing real-time feedback on the download status.

- **Rate Limiting**:
  - Implement a short sleep interval between downloads to respect YouTube's rate limits.

## 4. Video Processing with YOLOv8

### Input:
- `downloaded_path`: File path of the downloaded video.
- `video_id`: Unique identifier of the video.

### Steps:

#### Initialize Video Capture:
- Open the downloaded video file using OpenCV's `VideoCapture`.
- If the video fails to open, log the error and skip processing.

#### Retrieve Video Properties:
- Obtain video dimensions (width, height) and frame rate (fps).

#### Set Up Video Writer:
- Define the codec and initialize `VideoWriter` to save the processed video in `processed_dir` with the filename prefixed by "processed_".

#### Frame-by-Frame Processing:
While the video has frames:

- **Read Frame**:
  - Capture the current frame from the video.

- **Object Detection**:
  - Use the YOLOv8 model to detect objects within the frame.
  - Specifically, identify detections belonging to the person class (assumed to be class ID 0).

- **Bounding Box Extraction**:
  - If a person is detected:
    - Extract the bounding box coordinates (`x1`, `y1`, `x2`, `y2`).
    - Crop the frame to the bounding box, isolating the baby.
  - If no person is detected:
    - Optionally, write the original frame or skip.

- **Write Processed Frame**:
  - Save the cropped (or original) frame to the processed video file.

#### Finalize Processing:
- Release both `VideoCapture` and `VideoWriter` objects.
- Log the successful saving of the processed video in `processed_videos`.

#### Handle Processing Failures:
- If any errors occur during processing, log the `video_id` and error message for later review.

## 5. Data Management and Logging

### Steps:

#### Save Video Metadata:
- Compile all video metadata into a Pandas `DataFrame`.
- Save the `DataFrame` as a CSV file in `youtube_research_data` with a timestamped filename (e.g., "youtube_videos_20231027_123456.csv").

#### Log Failed Queries and Downloads:
- If there are entries in `failed_queries`, save them as a JSON file ("failed_queries.json") in `youtube_research_data`.
- Similarly, save `failed_downloads` as "failed_downloads.json" if any downloads failed.

## 6. Execution Flow

### Input:
- `research_queries`: List of search queries targeting diverse baby videos across different ethnicities.

### Steps:

#### Initialize Scraper:
- Instantiate the `YouTubeResearchScraper` class with appropriate parameters, including setting `processed_dir` to "yolo_processed_videos".

#### Execute Data Collection:
- Invoke the `collect_research_data` method with the following parameters:
  - `queries`: `research_queries`.
  - `max_results_per_query`: 25 (to efficiently reach the target of 500 videos).
  - `download`: True (to enable downloading and processing).
  - `resolution`: "720p" (desired video quality).
  - `target_total_videos`: 500 (total unique videos to download).

#### Monitor Progress:
- Observe the `tqdm` progress bars for download status.
- Review console logs for any processing or download errors.
- Check the `youtube_research_data` directory for CSV logs and JSON error logs.
