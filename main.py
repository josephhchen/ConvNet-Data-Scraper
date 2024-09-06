from scraper.video_scraper import VideoScraper
from video_processing.video_processor import VideoProcessor
from model.baby_detector import BabyDetector
import config

def main():
    scraper = VideoScraper(config.SEARCH_QUERY)
    videos = scraper.download_videos()
    
    detector = BabyDetector(config.MODEL_PATH)
    processor = VideoProcessor(detector)
    
    for video in videos:
        baby_video = processor.process_video(video)
        if baby_video:
            baby_video.save(f"baby_{video.name}")

if __name__ == "__main__":
    main()
