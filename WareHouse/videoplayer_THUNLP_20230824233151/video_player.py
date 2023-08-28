import cv2
class VideoPlayer:
    def __init__(self):
        self.video = None
    def load_video(self, file_path):
        """
        Load a video file from the given file path.
        """
        self.video = cv2.VideoCapture(file_path)
    def is_loaded(self):
        """
        Check if a video is loaded.
        """
        return self.video is not None
    def play(self):
        """
        Play the loaded video.
        """
        while True:
            ret, frame = self.video.read()
            if not ret:
                break
            cv2.imshow("Video Player", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        self.video.release()
        cv2.destroyAllWindows()