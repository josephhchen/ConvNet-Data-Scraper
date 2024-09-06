from .frame_extractor import FrameExtractor
from utils.video_utils import compile_frames_to_video

class VideoProcessor:
    def __init__(self, detector):
        self.detector = detector
        self.frame_extractor = FrameExtractor()
    
    def process_video(self, video_path):
        frames = self.frame_extractor.extract_frames(video_path)
        baby_frames = []
        
        for frame in frames:
            if self.detector.detect_baby(frame):
                baby_frames.append(frame)
        
        if baby_frames:
            return compile_frames_to_video(baby_frames)
        return None